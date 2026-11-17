# 03 — OpenAI, Gemini, DeepSeek: Provider-Neutral AI Design

## 1. Goals and separation of concerns

The application's **text reasoning provider** can be OpenAI, Gemini or DeepSeek; **embedding provider** is independently selected from OpenAI, Gemini, optional local or fake; **vision/media processing provider** is a separate future capability. Never choose a chat provider based on which embedding created the index. Do not assume DeepSeek provides a public embeddings endpoint. Provider credentials are exclusively server-side, and the web sees only allowlisted provider/model identifiers and health states.

## 2. Recommended default configurations

**Low operational complexity:** Gemini text generation + Gemini text embeddings for initial user testing, or OpenAI text + OpenAI embeddings. **Potential lower-cost text option:** DeepSeek for summaries/Q&A + Gemini/OpenAI embeddings. Do not claim a provider is always cheapest; compare live pricing, supported models and task quality when configuring.

Model IDs must be **environment-configurable** and allowlisted. As of November 2026, DeepSeek docs show `deepseek-flash` and `deepseek-v4-pro`, but providers can change their model catalogs. For Gemini, current docs recommend the Interactions API for new projects; `generateContent` is still supported. For OpenAI, Responses API is recommended for direct text requests. Use vendor-supported SDK methods, not an invented universal syntax.

| Capability | OpenAI | Gemini | DeepSeek |
| --- | --- | --- | --- |
| Text generation | Responses API | Interactions API preferred, `generateContent` compatible | OpenAI-compatible Chat Completions or Responses (per supported endpoint) |
| Structured JSON | Native schema where supported + Pydantic | JSON Schema/Pydantic + server validation | JSON mode + Pydantic; handle empty/invalid output |
| Text embeddings | Yes | Yes (`gemini-embedding-001` or compatible) | Not assumed / no embedding adapter without official evidence |
| Image/video understanding | Model-dependent, separate adapter | Model-dependent, separate adapter | Model-dependent, separate adapter; capability-checked |
| Streaming | Adapter implementation required | Adapter implementation required | Adapter implementation required |

## 3. Python interfaces (contracts, not installed code)

```python
from dataclasses import dataclass
from typing import Protocol, Any

@dataclass(frozen=True)
class ModelRequest:
    purpose: str                   # video_summary|playlist_summary|grounded_qa
    instructions: str
    user_input: str
    evidence: list[dict[str, Any]]
    response_schema: dict[str, Any]
    max_output_tokens: int
    temperature: float
    timeout_seconds: int
    prompt_version: str

@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int | None
    output_tokens: int | None
    provider: str
    model: str
    request_id: str | None

@dataclass(frozen=True)
class ModelResult:
    parsed: dict[str, Any]
    usage: ModelUsage

class TextModel(Protocol):
    async def generate_structured(self, request: ModelRequest) -> ModelResult: ...
    async def health(self) -> dict[str, str]: ...

class EmbeddingModel(Protocol):
    @property
    def profile_id(self) -> str: ...
    @property
    def dimensions(self) -> int: ...
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...
```

Need feature flags `supports_json_schema`, `supports_stream`, `supports_vision`, `max_context_tokens`, `supports_batch`. Do not smuggle provider-specific parameters into domain services; adapters translate from typed core requests.

## 4. Adapter behavior

- `OpenAITextAdapter`: call official `openai` SDK `responses.create`; map instructions/user input/structured output per selected model's capabilities; normalize output and usage; handle content filtering/retry errors.
- `GeminiTextAdapter`: call official `google-genai` SDK; prefer Interactions when production-compatible and feature coverage is tested, otherwise documented `generate_content` with ADR explaining decision. Supply JSON Schema or typed model when supported. Adapter must not rely on conversation state living on provider for source truth.
- `DeepSeekTextAdapter`: call documented DeepSeek endpoint with base URL `https://api.deepseek.com`; choose configured allowlisted model; JSON mode needs explicit JSON instruction. Handle empty output, malformed JSON and provider failures with bounded retry. Never leak reasoning traces or secrets into UI/logs.
- `FakeTextAdapter`: deterministic static fixture outputs for summaries/Q&A, recording request payload shape; no network.
- `OpenAIEmbeddingAdapter`, `GeminiEmbeddingAdapter`, `FakeEmbeddingAdapter`: assert vector dimension, reject NaNs/infs/length mismatch, batch and rate-limit with per-vendor limits.

**Provider error policy:** map 401 -> `PROVIDER_CONFIGURATION_ERROR` (never retry), 429/5xx -> `PROVIDER_TEMPORARILY_UNAVAILABLE` (bounded backoff), content safety refusal -> `PROVIDER_REFUSED`, malformed structured response -> validate then retry at most once with schema clarification, otherwise fail safely. Don't silently switch to a different paid provider: explicit workspace-level fallback opt-in only.

## 5. Configuration example (safe template)

```dotenv
APP_ENV=development
AI_CHAT_PROVIDER=fake
AI_CHAT_MODEL=fake-chat-v1
AI_EMBED_PROVIDER=fake
AI_EMBED_MODEL=fake-embed-v1
AI_EMBED_DIMENSIONS=64
AI_REQUEST_TIMEOUT_SECONDS=45
AI_MAX_OUTPUT_TOKENS=1800
AI_MAX_INPUT_CHARACTERS=120000
AI_MAX_RETRIES=2
OPENAI_API_KEY=
GEMINI_API_KEY=
DEEPSEEK_API_KEY=
YOUTUBE_API_KEY=
```

Use separate real profile values when activated, e.g. `AI_EMBED_PROVIDER=gemini`, `AI_EMBED_MODEL=gemini-embedding-001`, `AI_EMBED_DIMENSIONS=<verify-supported-dimensions>`. **Do not copy `64` into a real embedding configuration.** Validate dimensions with a real sample embedding before creating the collection; hard fail on mismatch. Model IDs for OpenAI and Gemini should be chosen from current official catalogs when the user sets up their keys; no automatic silent upgrades.

## 6. Provider selection lifecycle

1. Admin configures allowable providers/models server-side; keys in secret store or local `.env` (ignored by git).
2. App settings show available names and estimated capabilities without disclosing credentials.
3. Workspace text-provider selection is saved; each run snapshots provider/model/parameters to `provider_runs`.
4. Embedding profile is **deployment-level** for MVP; switching profiles requires migration/reindex workflow, not instantaneous UI toggle. Never mix dimensions in same collection.
5. For each change, run `FakeModel` tests, schema tests, provider adapter tests, optionally single paid `smoke` call with confirmation, and a golden Q&A comparison.

## 7. Structured generation + untrusted evidence

Use Pydantic v2 response schema and server evidence validation **after** model output. Construct prompts with separate sections: system/developer policy; user question; source evidence in explicit delimiters with IDs; output schema. Evidence content may include malicious instructions. Treat it as **data only**. Generated `citation_segment_ids` must be a subset of presented evidence IDs and must resolve in the authenticated workspace, or fail closed.

### Context and cost control

- Short summaries from chunk-level evidence, no entire 10-hour playlist in one call.
- Content-aware cache key `(source_revision,prompt_version,model,parameters)`.
- Provider rate-limit tokens/minute with semaphore, exponential retries and circuit breaker.
- Store request/response token counts or estimate where provider usage absent; clearly flag estimated numbers.
- Cap per-user or workspace daily tasks and provider spend estimate; prevent parallel duplicate processing.
- Do not implement all three providers as live-required for local tests. Real adapters compile, fake tests run without credentials.

## 8. Provider acceptance tests

- Contract tests for identical schemas from fake adapters and mocked all three real adapters.
- Timeout, 429, 401, empty JSON and wrong-dimension tests.
- User selects DeepSeek text + Gemini embeddings; no backend attempts to call DeepSeek embeddings.
- Switching text provider leaves Qdrant index unchanged.
- Changing embedding dimension fails with actionable reindex error; source data is preserved.
- Secret is never returned in settings responses or logs.

## 9. Official references

- OpenAI text: https://developers.openai.com/api/docs/guides/text
- OpenAI embeddings: https://developers.openai.com/api/docs/guides/embeddings
- Gemini Interactions: https://aistudio.google.com/docs/interactions-overview
- Gemini structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Gemini embeddings: https://ai.google.dev/gemini-api/docs/embeddings
- DeepSeek initial API: https://api-docs.deepseek.com/guides/codex
- DeepSeek JSON: https://api-docs.deepseek.com/guides/json_mode/
- DeepSeek models: https://api-docs.deepseek.com/quick_start/pricing/
