# LearnLens agent working agreement

This workspace includes a complete design in `docs/` and bounded sequential implementation prompts in `prompts/`. On each request, follow only the named phase. Do not infer or build later phases. Maintain provider-neutral text model adapters (OpenAI/Gemini/DeepSeek) and separate embedding providers (OpenAI/Gemini), authenticated tenant isolation, evidence-validated citations, and permissioned transcript ingestion. See `.cursor/rules/*.mdc` for precise scoped rules. Use fake providers for offline tests. Run tests, list modified files, report blockers, and stop.

**Git workflow:** Do all development on `dev` (synced from `main` at session start). Commit on `dev`, push, then merge to `main` at the end of each session. Do not develop directly on `main`.
