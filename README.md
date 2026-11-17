# LearnLens AI — Cursor/Grok Development Blueprint

**Version:** 1.1 · **Updated:** 2026-11-17 · **Status:** design package (Neon + Qdrant Cloud)

Build an evidence-grounded YouTube and authorized-media learning companion with playlist summaries, hierarchical topic notes, citation-based Q&A, formal SaaS UX, and configurable OpenAI / Gemini / DeepSeek model providers.

**Data stores:** Neon (free cloud Postgres) + Qdrant Cloud (free tier). No local database volumes required.

**Immediate entry point:** [`START_HERE_IN_CURSOR.md`](START_HERE_IN_CURSOR.md) · **Prompt index:** [`PROMPT_SEQUENCE.md`](PROMPT_SEQUENCE.md).

## Start here

1. Read `docs/00_MASTER_DESIGN.md` (product and technical requirements).
2. Read `docs/04_INGESTION_AND_COMPLIANCE.md` before promising any arbitrary public-video transcripts.
3. Read `docs/03_AI_PROVIDER_ROUTING.md` and pick **separate** chat and embedding providers.
4. Create a free Neon project and a free Qdrant Cloud cluster. Put the connection details in `.env` (never commit).
5. Open the **folder containing this README** as your Cursor workspace; `.cursor/rules/*.mdc` will apply automatically by scope.
6. Start Cursor Agent with Grok, attach **only** `prompts/00_PROJECT_SETUP.md` and the referenced docs. Finish, test, and commit before `01_...`.
7. For each phase, paste the matching prompt into a **new Cursor Agent chat**, read the completion report, verify tests yourself, and commit.
8. Record completion and outstanding issues in `checklists/PHASE_TRACKER.md`.

## Document index

| File | Purpose |
| --- | --- |
| `docs/00_MASTER_DESIGN.md` | Product, scope, NFRs, capabilities, critical flows, release gates |
| `docs/01_SYSTEM_ARCHITECTURE.md` | Component design (Neon + Qdrant Cloud), sequence, repository layout |
| `docs/02_DATA_AND_API_CONTRACTS.md` | PostgreSQL schema (Neon), Qdrant payload, REST APIs, error and citation contracts |
| `docs/03_AI_PROVIDER_ROUTING.md` | OpenAI/Gemini/DeepSeek adapters, embeddings, cost, structured outputs |
| `docs/04_INGESTION_AND_COMPLIANCE.md` | YouTube limitations, permissions, content states, playlist lifecycle |
| `docs/05_RAG_SUMMARIZATION_AND_EVAL.md` | Segmentation, hierarchical summaries, retrieval, factual verification |
| `docs/06_SECURITY_GUARDRAILS.md` | Identity, authorization, AI risks, input/output safeguards, testing |
| `docs/07_UI_UX_DESIGN_SYSTEM.md` | Formal visual language, layouts, states, accessibility and frontend specs |
| `docs/08_DEVOPS_OBSERVABILITY_COST.md` | Environments, free-tier notes, telemetry, budget controls |
| `docs/09_TEST_AND_RELEASE_PLAN.md` | Test pyramid, golden dataset, smoke and acceptance gates |
| `docs/10_ADRS.md` | Explicit architectural decisions (Neon + Qdrant Cloud) |
| `docs/11_SOURCES.md` | Official API docs and academic papers, dated and linked |

## How prompts are split

`00–16` are **sequential, small bounded implementation steps**. `17` and `18` are optional post-MVP extensions. Each prompt tells Grok which files to inspect, exactly what to implement, what not to change, what tests to run, and when to stop.

| Sequence | Phase |
| --- | --- |
| 00 | Workspace setup, repo rules, Makefile, architecture freeze |
| 01 | Cloud connections (Neon + Qdrant Cloud), minimal frontend/backend vertical slice |
| 02 | Neon schema migrations, domain models, authentication and tenancy |
| 03 | OpenAI/Gemini/DeepSeek providers + fake provider |
| 04 | YouTube URL parser, videos/playlist metadata, coverage states |
| 05 | Authorized captions/transcript upload + durable jobs |
| 06 | Content normalization, chaptering and per-video summaries |
| 07 | Embeddings, Qdrant Cloud hybrid retrieval, isolated indexing |
| 08 | Grounded video/playlist Q&A with verified citations |
| 09 | Formal design system, shell and responsive navigation |
| 10 | Library, playlist and video detail screens |
| 11 | Lesson reader, AI chat, citations and progress states |
| 12 | Structured notes and playlist synthesis |
| 13 | Security controls and adversarial red-team tests |
| 14 | Evaluation harness and performance regression checks |
| 15 | Monitoring, cost controls and worker reliability |
| 16 | CI, container deployment, docs, production readiness |
| 17 | **Optional:** authorized media / multimodal visual analysis |
| 18 | **Optional:** quizzes, tutoring and knowledge graph |

## Budget-smart Cursor workflow

- **Do not paste the entire package into every chat.** Start with the phase prompt; refer to docs by file path.
- Use one Cursor chat per phase.
- Use `fake` AI adapters and fixture transcripts until phases 03–08 pass. Then run a very small live smoke test with your chosen real provider.
- Keep auto-run commands limited to lint, unit tests and local integration tests.
- Neon and Qdrant Cloud free tiers are sufficient for development; monitor usage in their dashboards.
