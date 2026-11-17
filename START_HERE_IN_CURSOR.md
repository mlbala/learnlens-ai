# Start building LearnLens AI in Cursor

**Data stores:** Neon (free cloud Postgres) + Qdrant Cloud (free tier).

1. Extract this folder into a **new project folder**, open that folder in Cursor, and ensure hidden `.cursor/` rules are visible.
2. Create a free **Neon** project and a free **Qdrant Cloud** cluster. Copy the connection strings into a local `.env` file (never commit it).
3. Select **Grok** in Cursor Agent. Start a **new Agent chat** (not Ask-only mode).
4. Paste the content of `prompts/00_PROJECT_SETUP.md` into the chat, or attach it with `@prompts/00_PROJECT_SETUP.md`. Mention that the files in `docs/` are authoritative.
5. After Grok stops, run the tests it reports and review the files. Commit the accepted phase.
6. Start a **new chat** for `prompts/01_INFRA_VERTICAL_SLICE.md`. Continue to phase 16, in order, updating `checklists/PHASE_TRACKER.md`.
7. Phase 17 and 18 are optional; only run with explicit consent/need.

**Provider setup (not needed in phase 00):** Start with `AI_CHAT_PROVIDER=fake` and `AI_EMBED_PROVIDER=fake`. Once local tests pass, choose OpenAI, Gemini or DeepSeek for text. For real embeddings choose OpenAI or Gemini. Set API keys only in a local `.env` ignored by git.

**Warning:** Public YouTube URLs alone cannot guarantee transcripts; the compliant MVP requires authorized SRT/VTT/TXT content. Never ask the coding agent to bypass YouTube access restrictions.

**Workflow tip:** Use a new chat per phase, avoid attaching all docs at once, request no more than one bounded repair, and never permit surprise paid API usage, dangerous deletes, or deployment commands. Rely on fake-provider tests to control cost. Neon and Qdrant Cloud free tiers are sufficient for the entire development sequence.

**Direct copy prompt to start:**

```text
Implement phase 00 only from @prompts/00_PROJECT_SETUP.md. Follow @AGENTS.md and the listed architecture docs. First summarize a short implementation plan, then make scoped changes, run tests and stop with a completion report. Do not implement phase 01 or make paid API calls.
```
