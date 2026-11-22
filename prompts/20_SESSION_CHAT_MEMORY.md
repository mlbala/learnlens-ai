# Session 2 — Stored chat history and follow-up memory

**New Cursor Agent chat. Model: Grok 4.7 high and fast.** Paste only this session. Prerequisite: session 1 is accepted.

## Purpose
Ask AI on a lesson must remember earlier turns after a refresh. Memory is rows in Neon. The live search checkbox controls whether earlier outside-search text may enter the next prompt.

## Locked evidence contract
The study session is `chat_threads.id` for one workspace plus one lesson video.

Session 1 stored the video as `transcript_segments` under `source_kind = gemini_youtube`. Those rows are `evidence_origin = video_transcript` and `evidence_provider = gemini_youtube`. This session stamps them with the thread id. It does not embed them and it does not insert outside-search passages.

| What is stored on a turn | Where |
| --- | --- |
| User question | `chat_messages.content` |
| Live checkbox | `external_search_enabled` on that user message |
| Assistant lesson panel | `content_json.lesson` |
| Assistant outside panel, only if the checkbox was on for that turn | `content_json.external` plus `sources` with `evidence_provider` of `tavily`, `semantic_scholar`, or `openalex` |

Packing a follow-up, using the live checkbox on the new question:

- Checkbox off, including after it was on: send the last 8 turns’ user questions and lesson panels only. Omit earlier `external` bodies and their source URLs. Those rows stay in Neon.
- Checkbox on: send the last 8 turns with each block labeled. Lesson text is `video_transcript`. Earlier outside text is `external_search`. The labels tell the model that outside text is not the video.
- Never send turns from another lesson, thread, or workspace.

Neon holds the text. Qdrant is unchanged in this session. Do not add MongoDB. Do not download the YouTube file. Do not invent timestamps.

## Current state you must preserve
- Live Gemini answers go through `FixtureLessonClient.postMessage` in `apps/web/lib/lesson/client.ts`, which calls `POST /api/gemini-ask`. Threads live in the in-memory map in `apps/web/lib/lesson/fixtures.ts` and disappear on refresh.
- Postgres already has `chat_threads`, `chat_messages`, and `message_citations` in `apps/api/app/db/models/chat.py`. `chat_messages.content_json` can hold the structured answer. `chat_messages` already has `explanation_mode`.
- Answers are JSON `v: 1` with `lesson`, `external`, and `sources`, rendered by `apps/web/components/lesson/answer-view.tsx`. Keep that renderer.
- Ask AI sits under the video. Study notes stay on the right. Explanation modes are Brief, Detailed, and Technical. The checkbox “Search academic papers and official docs” stays, default checked.
- `POST /api/gemini-ask` already accepts `question`, `transcript`, `title`, `explanationMode`, and `externalSearch`. Search uses Semantic Scholar and OpenAlex, plus Tavily only when `TAVILY_API_KEY` is set.

## Read first
`AGENTS.md`, `docs/02_DATA_AND_API_CONTRACTS.md`, `apps/api/app/db/models/chat.py`, `apps/api/app/db/models/transcript.py`, `apps/web/app/api/gemini-ask/route.ts`, `apps/web/components/lesson/chat-panel.tsx`.

## Implement only this
1. One chat thread per workspace plus lesson video. `scope_kind = video` and `scope_id` is the lesson video id. Create it on the first question if it does not exist.
2. After the thread exists, set `thread_id` on that lesson’s `transcript_segments` in the same workspace. A segment keeps its session-1 id. A second workspace’s copy of the same YouTube id keeps its own thread.
3. Persist every user question and assistant answer. Store `external_search_enabled` on the user message. Store the structured answer in `content_json` and a plain-text fallback in `content`. Source objects stored from this turn keep their provider name.
4. On load, the Ask AI panel reads that thread from the API. Refresh keeps the conversation, including whether each turn had search on.
5. A follow-up sends the new question plus the packed last 8 turns, using the live-checkbox rule above. The model must treat “explain that”, “give an example”, and “why” as referring to the previous lesson answer. When the checkbox is now off, “explain that” refers to the lesson panel, not to an earlier paper summary.
6. The current question still runs the existing search only when its own checkbox is on. Saved sources are not a new search of old questions. Do not write those hits into `transcript_segments`.
7. A thread id from another workspace returns 404. Do not log full transcript or answer bodies.

## Out of scope
Qdrant indexing, reranker, reviewer, judge scores, changing `learning_history_limit`, new vendors.

## Acceptance
- Ask two follow-up questions, refresh, and both answers are still on the lesson.
- The lesson’s segment rows now carry this thread’s id, and the segment ids did not change.
- A follow-up that says “explain that” with the checkbox off receives the previous lesson panel and does not receive the previous external panel.
- The same follow-up with the checkbox on receives both panels, labeled by origin.
- A thread id from workspace A is not readable or writable as workspace B.
- The answer UI still shows the cards, not raw `###` markdown.
- Offline tests use a fake model. No paid call is required for unit tests.

## Tests
API tests for create-on-first-message, one thread per lesson, segment `thread_id` backfill, last-8 packing with the checkbox off and on, and cross-tenant 404. Web test that the panel renders messages returned by the client. Run the targeted tests plus lint and typecheck.

## Done means
Reply with implemented, files changed, tests and results, one manual check, risks, and a suggested commit message. Do not commit, push, or start the next session unless the operator asks. Then stop.
