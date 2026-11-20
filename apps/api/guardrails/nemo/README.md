# NeMo Guardrails (LearnLens)

**Why NeMo:** NVIDIA NeMo Guardrails is the actively maintained programmable guardrail framework
for input/output/retrieval rails. Protect AI **LLM Guard was archived in July 2026** and should
not be adopted for new work.

**Architecture rule (docs/06):** NeMo *augments* deterministic gates (auth, citation membership,
schema, size). It is never the single safety perimeter.

## Enable

```bash
# From apps/api
uv sync --extra guardrails --extra guardrails-ml
```

```env
AI_GUARDRAILS_BACKEND=nemo
AI_GUARDRAILS_NEMO_CONFIG=apps/api/guardrails/nemo
AI_GUARDRAILS_HF_MODEL=ProtectAI/deberta-v3-base-prompt-injection-v2
AI_GUARDRAILS_HF_THRESHOLD=0.5
```

## Behavior

| Channel | High-risk injection | Policy |
| --- | --- | --- |
| User chat question (direct) | BLOCK | 422 `PROMPT_INJECTION_BLOCKED` |
| Transcript / RAG evidence (indirect) | QUARANTINE | Kept as untrusted quoted data; never elevated to instructions |
| Model output | BLOCK / sanitize | Unsafe URLs/PII stripped; rail may refuse |

Offline CI defaults to `AI_GUARDRAILS_BACKEND=structured` (multi-signal Unicode/role/intent
scanner) so tests do not download torch/model weights.
