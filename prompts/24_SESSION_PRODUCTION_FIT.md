# Session 6 — Production fit for history, chat, cache, and both evidence origins

**New Cursor Agent chat. Model: Grok 4.7 high and fast.** Paste only this session. Prerequisite: session 5 is accepted.

## Purpose
Recent Learning, My Library, and the open lesson must show the same Neon lesson. Trimming a lesson must remove both evidence origins. Failures must be understandable, and logs must not contain the transcript or the search snippets.

## Locked evidence contract
Neon is the system of record.

- `video_transcript` / `gemini_youtube` rows are `transcript_segments`, stamped with the lesson’s `thread_id`.
- `external_search` rows are `external_evidence` for that same `thread_id`, with provider `tavily`, `semantic_scholar`, or `openalex`.
- Qdrant points are derived. Payload includes `workspace_id`, `video_id`, `thread_id`, `evidence_origin`, `evidence_provider`, and `content_hash`.
- The live checkbox still filters retrieval. Search off reads `video_transcript` only. Search on reads two lanes and keeps the video lane first.
- Redis may cache the lesson body only. It must not cache a retrieval result, a mixed prompt, or outside snippets.
- Deleting a lesson deletes, for that workspace and video: the lesson, its source asset, its transcript segments, its `external_evidence` rows, its chat thread and messages, and both origins of its Qdrant points. Another workspace is untouched.

Do not add MongoDB. Do not download the YouTube file. Do not change the embedding dimension.

## Current state you must preserve
- `learning_history_limit` defaults to 10, minimum 1, maximum 100, and is already editable.
- Ask AI is under the video. Notes are on the right. Answers render through `AnswerView`.
- Reviewer can withhold. Judge scores are stored and are not shown to learners.
- Docker web service is `learnlens-web:local`. It receives `GEMINI_API_KEY`, `AI_CHAT_MODEL`, and `TAVILY_API_KEY` from compose. Do not bake secrets into the image. Do not commit `.env`.

## Read first
`AGENTS.md`, `docs/02_DATA_AND_API_CONTRACTS.md`, `docs/06_SECURITY_GUARDRAILS.md`, `compose.yaml`, `apps/web/app/recent/page.tsx`, `apps/web/app/settings/page.tsx`, `apps/api/app/core/observability/`.

## Implement only this
1. Settings shows the current `learning_history_limit`. Saving it trims that workspace to the new limit. Recent Learning and My Library match on the next load. If session 1 already rendered the control, extend that control. Do not add a second one.
2. Opening a lesson from Recent Learning, My Library, or `/videos/{id}` loads the same Neon lesson, the same segment ids, and the same chat thread.
3. Redis, when `REDIS_URL` is reachable and caching is enabled by a setting that defaults off in tests, may cache the saved lesson body for at most 10 minutes. Key is `workspace_id` plus `video_id` plus lesson `content_hash`. A trim, a replaced lesson, or a segment change deletes that key. If Redis is down, read Neon and continue. Do not put `external_evidence` snippets or Qdrant hits in this cache.
4. User-visible failures, each one sentence plus a retry action:
   - Gemini busy
   - reviewer withheld the answer
   - search is on and lane B is empty, while the video answer still renders
   - the lesson is not in this workspace
   Do not show stack traces, keys, or raw provider payloads.
5. Record one audit-safe usage line per answer: workspace id, video id, thread id, decision, review status, `external_search_enabled`, count of kept video passages, count of kept outside passages, and token counts if the provider returned them. The line has no transcript text, no snippet, no URL query, and no source title.
6. Add a short operator note in `docs/02_DATA_AND_API_CONTRACTS.md` for the history limit, thread ownership, the two evidence origins, the checkbox filter, and the Redis lesson-body key. Do not rewrite the rest of the doc.

## Out of scope
New agents, new judge metrics, new databases, YouTube download, changing embedding dimensions, showing judge scores.

## Acceptance
- Changing the limit from 10 to 2 leaves 2 lessons in both library and recent, and the removed lessons have no remaining segments, external rows, or Qdrant points in that workspace.
- Redis down still opens a lesson from Neon. Test this with a failing cache stub.
- A cached lesson body does not contain an outside snippet. A unit test writes a snippet and asserts it is absent from the cache payload.
- Withheld, busy, and empty-search states render in the chat panel. Empty search still shows the video answer when the video lane hit.
- The usage line has no transcript text. A unit test feeds a transcript and a Tavily snippet and asserts both are absent.
- Workspace B cannot open workspace A’s recent list.

## Tests
API tests for trim across Neon and the vector delete function, cache bypass when Redis fails, cache payload contents, and log redaction. One web test for the withheld state and one for empty search beside a video answer. Run targeted tests, lint, and typecheck.

## Done means
Reply with implemented, files changed, tests and results, one manual check, risks, and a suggested commit message. Do not commit or push unless the operator asks. Then stop.
