# 10 — Architecture Decision Records

> ADRs are small, explicit and revisited only with measurements, security findings or API policy changes.

### ADR-001 — Modular monolith, not microservices
**Decision:** FastAPI business modules plus separate Celery process, shared app package. **Why:** maintainability and easy local build within finite Cursor budget. **Consequence:** service domains must be cleanly separated, avoid cross-layer imports.

### ADR-002 — Separate text and embeddings providers
**Decision:** OpenAI/Gemini/DeepSeek text adapters; OpenAI/Gemini embedding adapters. **Why:** text model choice should not force index reconstruction; DeepSeek embedding availability not assumed. **Consequence:** explicit embedding profile and collection version migration.

### ADR-003 — Qdrant Cloud for hybrid retrieval
**Decision:** Qdrant Cloud (free tier for development) for dense + lexical/BM25 hybrid search with RRF fusion and authenticated tenant filters. PostgreSQL (Neon) remains the source of truth. **Why:** free cloud vector store that matches the existing design, good hybrid search, no local disk pressure on the developer machine. **Consequence:** free-tier limits (1 GB RAM / 4 GB disk) must be monitored; idle clusters can be suspended.

### ADR-004 — Source truth in Neon Postgres
**Decision:** Neon (cloud Postgres) holds transcript spans, references, ownership and job status; Qdrant Cloud is a derived index only. **Why:** relational provenance, reliable deletion, correct citations, and free cloud Postgres without local storage cost. **Consequence:** answer evidence hydrating and index consistency required between Neon and Qdrant.

### ADR-005 — Authorized transcripts first
**Decision:** URL fetches metadata only unless lawful transcript/media provided. **Why:** YouTube API caption permission restrictions. **Consequence:** some public videos cannot be summarized from URL alone; honest UI coverage needed.

### ADR-006 — Deterministic worker pipeline before autonomous agents
**Decision:** explicit functions/tasks for parse, chunk, summarize, index, validate. Add LangGraph only for demonstrably useful stateful reasoning. **Why:** cost, debugging and prompt-injection surface. **Consequence:** fewer 'agents' than marketing might suggest.

### ADR-007 — Server-validated citations
**Decision:** model can return evidence IDs only; server derives title/time/link. **Why:** prevents forged timestamps and cross-tenant citations. **Consequence:** evidence schema and strict validation required.

### ADR-008 — Formal design language
**Decision:** neutral canvas, single blue accent, 8px radius, semantic UI, almost zero gradients. **Why:** premium enterprise feel and learner concentration. **Consequence:** frontend may not improvise branding per page.

### ADR-009 — First-party session auth for local reproducibility
**Decision:** backend-managed Argon2id accounts and secure cookie sessions, CSRF protection, hashed refresh rotation. **Why:** no dependency on hosted auth during local development. **Consequence:** more auth implementation and security testing work; consider managed identity for commercial SaaS if justified.

### ADR-010 — Fake provider as required testing baseline
**Decision:** all workflows test offline using deterministic fake text/embedding adapters. **Why:** reduce API costs and make CI reproducible. **Consequence:** real-model performance requires separate smoke + evaluation runs.

### ADR-011 — Multi-video coverage is a first-class data property
**Decision:** playlist summaries must state how many videos were analyzed. **Why:** titles without transcripts cannot substantiate a course summary. **Consequence:** partial coverage state propagates across UI and API.

### ADR-012 — React/Next.js frontend, containerized backend
**Decision:** optionally deploy web on Vercel; API/worker on container host; Neon + Qdrant Cloud as managed data stores. **Why:** long-running jobs and data stores are not serverless frontend concerns; free cloud tiers keep developer machines light. **Consequence:** deployment topology and CORS/cookie proxy must be documented.

### ADR-013 — Gemini text via generate_content for MVP adapters
**Decision:** `GeminiTextAdapter` calls official `google-genai` `generate_content` with JSON MIME type rather than the Interactions API. **Why:** Interactions is recommended for new Google projects, but `generate_content` remains supported, maps cleanly to our structured-output contract, and is straightforward to unit-mock without live calls. **Consequence:** revisit Interactions when streaming/tooling needs justify a migration; keep adapter boundary so domain services stay provider-neutral.

### ADR-014 — NeMo Guardrails + HF classifier over archived LLM Guard / regex-only PI
**Decision:** Prefer **NVIDIA NeMo Guardrails** as the programmable rails framework, with a local HuggingFace prompt-injection classifier (ProtectAI DeBERTa family) as the semantic detector. Keep deterministic gates (auth, citation membership, schema, size, OutputPolicy) as the fail-closed floor. Offline CI defaults to a structured multi-signal scanner (Unicode smuggling + role/delimiter frames + intent families), not regex-alone. **Do not adopt Protect AI LLM Guard for new work** (archived July 2026). **Why:** NeMo is actively maintained, supports input/output/retrieval rails and HF classifiers without making a generative self-check LLM the only detector; regex-only PI is brittle against novel attacks. **Consequence:** optional extras `guardrails` / `guardrails-ml`; set `AI_GUARDRAILS_BACKEND=nemo` or `hf` in production; never let a model judge replace tenant isolation or citation validation.
