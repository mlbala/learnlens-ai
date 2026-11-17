# LearnLens AI — Cursor Agent Prompt Sequence

Run each phase in a **new** Cursor Grok Agent chat. Complete all acceptance criteria, review git diff, run tests and commit before next. Phase 17–18 are opt-in.

| File | Deliverable |
| --- | --- |
| [`prompts/00_PROJECT_SETUP.md`](prompts/00_PROJECT_SETUP.md) | Project scaffolding and requirements freeze |
| [`prompts/01_INFRA_VERTICAL_SLICE.md`](prompts/01_INFRA_VERTICAL_SLICE.md) | Cloud connections (Neon + Qdrant Cloud) and minimal frontend/backend vertical slice |
| [`prompts/02_DATA_AUTH.md`](prompts/02_DATA_AUTH.md) | Schema migrations, users, workspaces and safe session authentication |
| [`prompts/03_AI_PROVIDER_ADAPTERS.md`](prompts/03_AI_PROVIDER_ADAPTERS.md) | Interchangeable OpenAI, Gemini and DeepSeek text adapters plus independent embeddings |
| [`prompts/04_YOUTUBE_METADATA.md`](prompts/04_YOUTUBE_METADATA.md) | YouTube URL validation, video import and playlist metadata enumeration |
| [`prompts/05_TRANSCRIPT_JOBS.md`](prompts/05_TRANSCRIPT_JOBS.md) | Rights-attested transcript upload and durable processing jobs |
| [`prompts/06_CHAPTERS_SUMMARY.md`](prompts/06_CHAPTERS_SUMMARY.md) | Segmentation and evidence-grounded per-video summarization |
| [`prompts/07_QDRANT_HYBRID.md`](prompts/07_QDRANT_HYBRID.md) | Qdrant Cloud indexing and workspace-isolated hybrid retrieval |
| [`prompts/08_GROUNDED_QA.md`](prompts/08_GROUNDED_QA.md) | Evidence-grounded RAG chat with verified timestamp citations |
| [`prompts/09_UI_DESIGN_SYSTEM.md`](prompts/09_UI_DESIGN_SYSTEM.md) | Formal enterprise-grade SaaS UI design system and app shell |
| [`prompts/10_LIBRARY_SCREENS.md`](prompts/10_LIBRARY_SCREENS.md) | Library, source import, video and playlist overview UX |
| [`prompts/11_LESSON_CHAT_UI.md`](prompts/11_LESSON_CHAT_UI.md) | Lesson reader, source time jumps, AI tutor and chat interfaces |
| [`prompts/12_PLAYLIST_SYNTHESIS.md`](prompts/12_PLAYLIST_SYNTHESIS.md) | Course-level summary and reusable learning notes |
| [`prompts/13_SECURITY_GATE.md`](prompts/13_SECURITY_GATE.md) | Defense-in-depth AI guardrails and adversarial security audit |
| [`prompts/14_EVAL_QUALITY.md`](prompts/14_EVAL_QUALITY.md) | Evaluation harness, quality baselines and regression gates |
| [`prompts/15_OBSERVABILITY_COST.md`](prompts/15_OBSERVABILITY_COST.md) | Operational reliability, telemetry, usage and spend budgets |
| [`prompts/16_CI_RELEASE.md`](prompts/16_CI_RELEASE.md) | Build, test, deploy and handoff production checklist |
| [`prompts/17_OPTIONAL_MULTIMODAL.md`](prompts/17_OPTIONAL_MULTIMODAL.md) | OPTIONAL: rights-authorized visual/audio understanding |
| [`prompts/18_OPTIONAL_TUTOR_GRAPH.md`](prompts/18_OPTIONAL_TUTOR_GRAPH.md) | OPTIONAL: adaptive tutoring, quizzes and concept graph |

Use `START_HERE_IN_CURSOR.md` first. Source-of-truth technical specifications: `docs/00_MASTER_DESIGN.md` through `docs/11_SOURCES.md`.
