# 00 — LearnLens AI: Master Product and Engineering Design

**Version:** 1.0 | **Date:** 2026-11-16 | **Owner:** product engineering | **Status:** implementation specification

## Executive summary

LearnLens AI turns permitted source content associated with YouTube videos and playlists into **grounded, navigable learning experiences**. It ingests official YouTube metadata, creator-authorized captions, or user-supplied licensed transcripts and (later) authorized media. It creates accurate chapter-level notes, hierarchical summaries, and question-answering with citations tied to video timestamps where timecoded evidence exists. It also offers easy/technical explanations and learning resources without pretending AI-generated analogies were spoken by the instructor.

**Non-negotiable boundary:** a pasted public YouTube URL alone does **not** guarantee access to a transcript or media. The YouTube Data API can enumerate playlists, but downloading captions requires permission to edit the video. The product must transparently show `needs_transcript`, `metadata_only`, or `not_authorized` states and allow lawful alternatives. Never implement bypasses, unauthorized media downloads or transcript scrapers in the core.

## 1. Product vision and positioning

- **Audience:** individual learners, engineers, students, creators, training organizations. Start with a personal workspace but build isolated multi-user foundations.
- **User promise:** go from authorized video material to an understandable learning path, cited answers, and reusable study notes.
- **Distinctive value:** source-grounded timestamped answers, per-video and cross-video hierarchy, coverage indicators, user-selectable explanation level, and objective evaluation.
- **Main UX:** Add URL > inspect playlist/video metadata > attach permitted transcripts > process and review coverage > study notes > ask source-grounded questions > jump to the source.
- **Formal brand:** LearnLens AI (working name); changeable via configuration. Enterprise SaaS aesthetic: neutral off-white/dark ink, modest cobalt/indigo accent, no large gradients, no playful glassmorphism.

## 2. Problem statement

Linear video learning has high time cost, low information accessibility, difficult cross-lecture concept discovery, and weak recall. Existing single-pass summarization can omit details, misattribute claims, or hallucinate timestamps. With multi-video playlists, naive concatenation risks model-context limits and inconsistent overall coverage. We need a transparent, recoverable information pipeline.

## 3. Goals and explicit non-goals

### MVP goals

G1. Accept valid YouTube video and playlist URLs and fetch metadata through official APIs.

G2. Enumerate every available playlist item via pagination and persist its position, ID, title, URL and status. Clearly signal unavailable, private or deleted entries.

G3. Import timestamped `.srt`/`.vtt`, plain `.txt` transcripts or pasted text with a recorded provenance and authorization attestation; provide authorized caption integration only for videos the connected owner can manage. Plain text supports summary and Q&A but **not verified video timestamps**.

G4. Process a video into normalized segments, chapter-level summary, full-video summary, concepts and evidence references.

G5. Process a playlist into summary of each **ready** video, cross-video topic clusters, aggregated syllabus, coverage counts, and honest missing-content notices.

G6. Answer questions limited to a selected video, playlist or library, with **checked retrieval citations** and fallback when evidence is absent.

G7. Allow OpenAI, Gemini or DeepSeek chat provider selection independently of embedding selection and preserve integration tests with fake providers.

G8. Multi-user secure isolation and strong guardrails. Reliable progress/status reporting, rate limits, operational logs and evaluation fixtures.

### Explicit non-goals for MVP

- Guaranteed automatic transcription for arbitrary public YouTube URLs.
- YouTube video or audio downloading without verified permissions and policy-compatible workflow.
- Automatically generating visual descriptions from source video without access to authorized media.
- Browsing arbitrary URLs, reading local files or executing instructions because a transcript told the model to.
- Fully autonomous internet research agent, massive graph database, mobile native app, collaborative organizations, public content sharing or multilingual speech synthesis.
- Claims that all playlist material is covered when any videos lack a transcript.

## 4. Personas and user stories

**Solo learner**: imports a 12-video communication course and wants digestible notes, a summary for each lecture, key takeaways and a question-answer assistant. If 3 lectures lack transcripts, UX reports 9/12 ready and never fabricates the missing 3.

**Technical engineer**: imports a LangGraph playlist, asks “where is conditional routing explained?”, receives a concise response with evidence spans and clickable YouTube time links where possible.

**Educator / content owner**: authorizes access to their own caption tracks or uploads exported SRT/VTT, generates lesson outlines and shares no information with other users by default.

**Operations administrator**: sees failed ingestion jobs, input cap hits, per-provider spend, latency and privacy-safe audit activity.

## 5. Functional requirements

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| F01 | YouTube link parsing | Recognize `youtube.com/watch`, `youtu.be`, `/playlist?list=`, `/shorts/`; reject non-YouTube hosts, ambiguous IDs and malformed URLs |
| F02 | Playlist metadata | Paginate official API; preserve order, duplicates policy and unavailable states; bounded max items configurable |
| F03 | Authorized content | Upload/import caption files and prove provenance; unsupported source has honest status |
| F04 | Background jobs | Queue asynchronous processing, persist stages, retry retryable failures, support idempotent replay |
| F05 | Segment model | Normalize timestamps/encoding, deduplicate overlaps; retain immutable source references |
| F06 | Summaries | Short overview, chapters, technical/simple takeaways, source-supported key points |
| F07 | Hierarchical playlist | Video summaries -> module/topic summaries -> course overview with per-video coverage |
| F08 | Search | Hybrid dense + lexical retrieval in Qdrant with enforced tenant and selection filters |
| F09 | Chat | Grounded responses, evidence citations, refusal for unsupported answer; history scoped to workspace |
| F10 | Explain | `simple`, `standard`, `technical` presentation styles, with non-source examples explicitly labeled |
| F11 | Provider switching | OpenAI, Gemini, DeepSeek text; embedding provider independently configured; diagnostics |
| F12 | Formal UI | Responsive accessible app, loading/error/empty states, keyboard support, no broad gradients |
| F13 | Security | Auth, RBAC/ownership, CSRF defense where applicable, upload validation, injection testing |
| F14 | Cost controls | Token accounting, configurable budget/quota, no unbounded processing loops |
| F15 | Deletion | Delete own collection with removal of relational, vector and authorized object content; auditable failure retries |

### Playlist coverage contract

A playlist holds `item_count_total`, `item_count_ready`, `item_count_missing`, `item_count_failed`, `item_count_unavailable` and `last_computed_at`. A playlist-wide summary must include `coverage_ratio`, `included_video_ids`, `excluded_video_ids`, caveats and an explicit 'partial' label unless every eligible video has supported content. Titles and descriptions alone are **not substitutes** for video content.

## 6. Non-functional requirements

- **Integrity:** every source-grounded citation maps to existing authorized content and a real stored source span. Never invent times.
- **Isolation:** data accessible only inside the authenticated user's permitted workspace; every SQL and Qdrant read has ownership scope.
- **Reliability:** idempotent content imports, durable worker execution, observable and recoverable failure statuses; no silent success on partial failure.
- **Availability target (initial):** local reproducibility; design for >=99.5% production application uptime after deployment and monitoring (goal, not current guarantee).
- **Performance target (initial):** warm list API p95 <500 ms for local/staging fixture data; query retrieval p95 <1.5 s; end-to-end AI response depends on provider and is separately measured. These are targets to verify, not promised benchmarks.
- **Scalability target:** MVP dev fixtures of 20 videos x 60 minutes; configurable project max 50 videos, transcription max 2 hours per uploaded asset, uploads capped by documented limits, worker concurrency 2; all are **configurable defaults**, not universal limits.
- **Cost:** display per-task model/token usage, enforce user request and ingestion limits, cache summaries, avoid duplicate jobs.
- **Maintainability:** Python 3.12+, strict typed API contracts, TypeScript strict, schema migrations, automated tests, explicit ADRs.
- **Privacy:** minimization, opt-in media uploads, content deletion, logs without transcript content or API keys, vendor selection disclosed.

## 7. Proposed technology and boundaries

| Concern | Choice | Rationale |
| --- | --- | --- |
| Web | Next.js App Router + TypeScript + Tailwind + shadcn/ui | Product-quality, accessible structured UI |
| API | FastAPI + Pydantic v2 + SQLAlchemy 2.x | Typed Python API and clean service boundary |
| DB | PostgreSQL + Alembic | Source of truth, provenance and reliable job state |
| Retrieval | Qdrant | Dense + sparse/BM25 hybrid RRF, payload isolation |
| Async workers | Celery + Redis | Bounded durable background stage orchestration |
| AI | Provider-specific adapters | OpenAI Responses, Gemini adapter, DeepSeek API |
| AI workflow | Explicit deterministic stages; LangGraph **only** when stateful branching justifies | Avoid costly, opaque agent loops |
| Auth | Backend-managed accounts, Argon2id, secure cookies + CSRF, rotating refresh sessions | Local reproducibility without external auth dependency |
| Source | Official YouTube Data API, permitted caption import | Legal/operational stability |
| Monitoring | Structured logs, OTel traces, metrics | Debug failures and measure spend |
| Storage | Local volume dev; S3-compatible object storage production | Secure authorized-upload storage |

## 8. Principal end-user workflows

### Flow A — Add video

1. User posts YouTube URL. Parser canonicalizes host and IDs; do not fetch arbitrary hosts.
2. API fetches metadata by official YouTube endpoint. Stores source URL, title, creator, duration if available and thumbnail references (respect YouTube policies).
3. Video detail shows `Awaiting transcript` with options: paste text; upload SRT/VTT/TXT; authorize the owner's caption integration (if implemented).
4. The user affirms they have rights/permission for submitted content; audit source type and attestation timestamp.
5. Background job validates -> normalizes -> segments -> generates summaries -> indexes and marks `ready` only when required artifacts pass validation.
6. View lesson reader and ask questions; citations link to spans and YouTube `?t=` only when timestamp authenticity is confirmed.

### Flow B — Add playlist

1. Fetch official playlist pages until finished or configured bound is reached; store item order, videos, metadata and status.
2. Set item statuses; bulk-import user provided transcript files matched by video ID or explicit manual selection.
3. Process per-video jobs concurrently with concurrency cap; allow reprocess one item.
4. Aggregate only supported ready items; produce coverage and 'partial/complete' label.
5. Cross-video Q&A filters retrieval by playlist-member video IDs belonging to tenant.

### Flow C — Ask a question

1. Validate authenticated workspace, question length and scope.
2. Retrieve dense + lexical candidates using mandatory tenant and resource filters; optionally rerank.
3. Build a constrained evidence packet (ordered source span IDs, text, verified start/end, source title).
4. Invoke the chosen text provider with untrusted evidence clearly separated from instructions.
5. Validate response schema, supported claim references and citation IDs. If no evidence: answer `Not covered by the available source material`.
6. Display answer, source list, source provenance and links. AI-added analogies labeled as examples.

## 9. Data provenance and trust model

Four trust levels: (1) server policy and authenticated identity, (2) user request, (3) external metadata, transcripts and retrieved chunks (untrusted), (4) LLM output (untrusted until validated). Only level (1) can authorize actions. A transcript may contain prompt injection; the system must never elevate transcript text to application instructions. Timestamp citations require stored timing; no timing -> section/caption text citations only.

## 10. Source data and processing statuses

Enumerated processing stages: `discovered`, `metadata_only`, `needs_transcript`, `queued`, `validating`, `normalizing`, `segmenting`, `summarizing`, `indexing`, `ready`, `failed_retryable`, `failed_terminal`, `not_authorized`, `unavailable`, `deleted`.

Content has `source_kind` (`user_uploaded_srt`, `user_uploaded_vtt`, `user_uploaded_txt`, `user_pasted`, `owner_authorized_caption`, `licensed_media`) and `timecode_quality` (`original_caption`, `verified_manual`, `none`). Never silently promote plain text to timestamps.

## 11. AI models and provider abstraction

- **Chat provider:** `openai`, `gemini`, `deepseek` and `fake` (tests). Model name is allowlisted and configured server-side. Never infer that all models have the same features.
- **Embedding provider:** `openai`, `gemini`, `local` (optional) and `fake`. **DeepSeek text-chat support does not imply a DeepSeek embeddings API**.
- **Different responsibilities:** chat model may switch between questions; embedding model/dimension ties to vector index. Reindex explicitly when changing embedding profile; never silently mix vectors.
- **Structured outputs:** provider-native where supported, followed by server Pydantic validation, bounded retries and a fail-closed state.
- **Provider APIs:** OpenAI Responses recommended for direct text requests; Gemini Interactions is currently the recommended API for new projects (older `generateContent` supported); DeepSeek supports OpenAI-compatible chat endpoints. Keep these behind adapters so release changes don't leak across core logic.

## 12. Milestone and release definition

**M0, Foundation:** Dockerized web/API/postgres/redis/qdrant work locally; strict API contract and auth.

**M1, Real value:** URL metadata + authorized transcript upload + summaries for each ready video with correct states.

**M2, Trustworthy intelligence:** Qdrant hybrid retrieval + grounded chat, evidence IDs, partial playlist summary.

**M3, Professional product:** polished responsive formal UI, library, lesson reader, chat and consistent status feedback.

**M4, Hardening:** threat controls, evaluation, telemetry, spend caps, tests, deploy instructions.

**Optional M5:** rights-cleared visual understanding; personalized teaching and quiz features.

Exit criteria for MVP: real fixture video + multi-video playlist flow works end to end; missing content is honest; auth isolation and adversarial tests pass; citations verified by application code; every required component can be booted with documented Docker steps; no API keys committed.

## 13. Delivery discipline for Cursor

Prompts `00–16` are bounded PR-sized work units; execute serially and **never start the next phase until tests pass and the prior phase is committed**. Reuse preexisting architecture and avoid refactoring earlier phases just for style. If blocked by missing credentials, implement a fake/local fixture path and report that the real integration was not live-verified. Each prompt ends with exact changed file paths, commands run, results, residual risks and commit recommendation.

## 14. Top risks, mitigations and ownership

| Risk | Mitigation | Gate |
| --- | --- | --- |
| Arbitrary YouTube captions inaccessible | Permissioned imports, honest coverage state, no scraping fallback | F03 / M1 |
| Hallucinated timestamps | Citation validator joins `source_span_id` to storage, requires original caption timecodes | M2 |
| Prompt injection in transcripts | Untrusted-content separation, no tool execution from evidence, adversarial suite | M4 |
| Cross-tenant vector retrieval | Mandatory server-derived tenant filter, negative isolation tests | M2 |
| Provider SDK drift | Adapter contracts, pinned dependency ranges, optional live smoke tests | M1 |
| Costs exceed plan | Provider usage ledger, caps, caching, max worker concurrency | M4 |
| Playlist has missing items | Persist and expose 9/12 coverage; partial summaries labeled | M2 |
| Overbuilding | Fixed MVP release gates; optional phases 17-18 not in critical path | All |

## 15. References

See `11_SOURCES.md`; official vendor docs and research are primary references, verified November 2026. Consult official documentation before pinning model IDs and SDK versions. Fees and API capabilities may change after this date.
