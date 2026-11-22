# Session 1 — Durable lessons, My Library, and Recent Learning

**New Cursor Agent chat. Model: Grok 4.7 high and fast.** Paste only this session. Do not start session 2.

## Purpose
Lessons built from a public YouTube URL, and the Recent Learning list, must survive a browser refresh. Neon Postgres is the system of record. This session also stores the video text as flagged passages so later sessions can embed it without guessing which text is the video.

## Locked evidence contract
One study session is one chat thread per workspace and lesson. This session does not create that thread. It stores the video side only.

| Field | Value in this session |
| --- | --- |
| `evidence_origin` | `video_transcript` |
| `evidence_provider` | `gemini_youtube` |
| `workspace_id` | the signed-in workspace |
| `video_id` | this lesson |
| `thread_id` | null until session 2 |
| `source_url` | the public watch URL |
| `content_hash` | hash of that passage’s text |
| `start_ms`, `end_ms` | null. Do not invent timestamps |

Full passage text stays in Neon. Do not write Qdrant. Do not write `external_search` rows. Do not download the YouTube file. Do not add MongoDB.

## Current state you must preserve
- Web library for live Gemini lessons is in-memory: `apps/web/lib/library/client.ts` (`FixtureLibraryClient`, `seedDemo: false`). A refresh drops imports.
- Gemini lesson build: `POST /api/gemini-lesson` in `apps/web/app/api/gemini-lesson/route.ts`. It calls Gemini with a public watch URL. It does not download the video. Retired models matching `gemini-2.5`, `gemini-2.0`, and `gemini-1.` are skipped. Working default is `gemini-3.5-flash-lite`, then `gemini-flash-lite-latest`, then `gemini-3.1-flash-lite`.
- Lesson UI already has study notes on the right and Ask AI under the player: `apps/web/components/lesson/lesson-reader.tsx`. Do not move that layout.
- Structured tutor cards exist: `apps/web/components/lesson/answer-view.tsx`. Do not revert them to raw markdown.
- Recent Learning is a placeholder: `apps/web/app/recent/page.tsx` renders `ComingSoon`. Nav item `recent` is `placeholder: true` in `apps/web/lib/navigation.ts`.
- Postgres models already exist for `videos`, `source_assets`, `transcript_segments`, `workspaces`. `transcript_segments` already requires real timestamps or both ends null. API is FastAPI. Database is Neon via `DATABASE_URL`. Qdrant is for embeddings only. Redis is optional and is not the history store.

## Read first
`AGENTS.md`, `.cursor/rules/*.mdc`, `docs/02_DATA_AND_API_CONTRACTS.md`, `apps/api/app/db/models/library.py`, `apps/api/app/db/models/transcript.py`, `apps/web/lib/library/client.ts`.

## Implement only this
1. Persist each successful Gemini lesson for the signed-in workspace in Neon: youtube video id, title, channel if known, summary, key points, source URL, `last_opened_at`. The source asset uses `source_kind = gemini_youtube`.
2. Split the lesson transcript into ordered `transcript_segments` with stable ids. Each row stores `workspace_id`, `video_id`, `ordinal`, `text`, `content_hash`, and null timestamps. These rows are the `video_transcript` passages. Keep the summary and key points on the lesson record, not as fake transcript timestamps.
3. Reopening the same video in the same workspace returns the saved lesson and the same segment ids. A different workspace cannot read the lesson or the segments.
4. Add workspace setting `learning_history_limit`, integer, default **10**, minimum 1, maximum 100. It is editable in Settings and honored by the server. Changing it immediately changes how many lessons are kept.
5. After each save or open, keep only the newest `learning_history_limit` Gemini lessons for that workspace. Delete the older lesson rows, their source assets, and their transcript segments for that workspace. My Library and Recent Learning both read this same saved set, newest `last_opened_at` first.
6. Replace the Recent Learning placeholder with that list. Each row opens the lesson. Empty state tells the user to paste a public YouTube link.
7. The browser must not be the only copy. Refreshing `/videos`, `/library`, and `/recent` shows the saved lessons.

## Out of scope
Chat threads, follow-up context, embedding, reranker, reviewer, LLM-as-judge, Redis, Tavily, Semantic Scholar, OpenAlex. Leave Ask AI behavior as it is.

## Acceptance
- Build a lesson, refresh, and the lesson is still in My Library and Recent Learning.
- The saved transcript is a list of segment rows with `source_kind = gemini_youtube`, stable ids, and null timestamps.
- An 11th lesson drops the oldest lesson and its segments when the limit is 10.
- Setting the limit to 3 leaves 3 lessons.
- A second workspace does not see the first workspace’s lessons or segments.
- No YouTube file is written to disk or object storage. No Qdrant write happens.
- Offline tests use fake providers and a test database. No paid call is required for unit tests.

## Tests
Add API tests for tenant isolation, the default limit, trimming segments with the lesson, reopen returning the same segment ids, and null timestamps. Add a web test that Recent Learning renders saved rows instead of Coming Soon. Run `make lint`, `make typecheck`, and the new tests. If `make test` is too broad, run the targeted pytest and `npm run test --workspace=@learnlens/web` for the new files, and say what you did not run.

## Done means
Reply with implemented, files changed, tests and results, one manual check, risks, and a suggested commit message. Do not commit, push, or start the next session unless the operator asks. Then stop.
