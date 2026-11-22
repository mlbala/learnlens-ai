# Session 3 — Index both origins, rerank inside each lane, then decide

**New Cursor Agent chat. Model: Grok 4.7 high and fast.** Paste only this session. Prerequisite: session 2 is accepted.

## Purpose
Embed the video passages and the outside-search hits as separate points on the same study session. Retrieval must be able to keep only the video when search is off, and must keep the video ahead of Tavily and papers when search is on.

## Locked evidence contract
The study session is `chat_threads.id` for one workspace and one lesson. Session 2 already stamped that id on the video segments.

Neon is the source of truth. Qdrant stores derived vectors and a short preview. Full text stays in Neon. Use the existing embedding profile and dimension. Do not add a new embedding vendor or a new dimension. Do not add MongoDB. Do not download the YouTube file. Do not invent timestamps.

Every Qdrant payload carries:

| Field | Video lesson | Outside search |
| --- | --- | --- |
| `evidence_origin` | `video_transcript` | `external_search` |
| `evidence_provider` | `gemini_youtube` | `tavily`, `semantic_scholar`, or `openalex` |
| `workspace_id` | the signed-in workspace | the same workspace |
| `video_id` | this lesson | this lesson |
| `thread_id` | this lesson’s chat thread | the same thread |
| `segment_id` or `evidence_id` | the Neon row id | the Neon row id |
| `source_url` | the public watch URL | the URL the searcher returned |
| `content_hash` | hash of the passage | hash of the snippet |
| `start_ms`, `end_ms` | null unless the Neon row already has both | null |

A point with no `evidence_origin` is invalid and must not be retrieved. Extend `ChunkIndexRecord` in `apps/api/app/retrieval/contracts.py`. Keep the existing `workspace_id` plus authorized `video_id` filter. Add `evidence_origin` and `thread_id` as payload indexes.

## Current state you must preserve
- Video text is already split into `transcript_segments` with stable ids, `source_kind = gemini_youtube`, and `thread_id` set.
- `POST /api/gemini-ask` searches with `apps/web/lib/search/topic-sources.ts` when `externalSearch` is true. Papers and official docs rank above other pages. Tavily runs only when `TAVILY_API_KEY` is set.
- The answer contract is JSON `v: 1` rendered by `apps/web/components/lesson/answer-view.tsx`.
- Follow-ups already pack the last 8 turns. Checkbox off already omits earlier external panels. Do not undo that packing.
- Existing hybrid retrieval in `apps/api/app/retrieval/` filters by workspace and video. Do not accept a filter from the browser.

## Read first
`AGENTS.md`, `docs/02_DATA_AND_API_CONTRACTS.md`, `docs/05_RAG_SUMMARIZATION_AND_EVAL.md`, `apps/api/app/retrieval/contracts.py`, `apps/api/app/retrieval/filters.py`, `apps/web/app/api/gemini-ask/route.ts`, `apps/web/lib/search/topic-sources.ts`.

## Implement only this
1. Add a Neon table `external_evidence` for outside hits only. Columns: id, `workspace_id`, `video_id`, `thread_id`, `message_id`, `evidence_origin` fixed to `external_search`, `evidence_provider`, title, source URL, snippet, `content_hash`, created time. Write a row only for a URL the searcher returned on a turn whose checkbox is on. Do not insert these rows into `transcript_segments`.
2. Index `video_transcript` points once per segment. Index `external_search` points for the current thread. Reuse an existing point when `workspace_id`, `thread_id`, `evidence_origin`, and `content_hash` match. Stamp both origins with the same `thread_id`.
3. Retrieval filter, before any score:
   - Checkbox off, including after the learner turns it off: `evidence_origin = video_transcript` for this workspace, video, and thread. Do not fetch, rerank, or send `external_search` points. Leave them stored so turning the checkbox back on can reuse them in this thread.
   - Checkbox on: two lanes. Lane A is `video_transcript` for this thread. Lane B is `external_search` for this same thread. Another thread, video, or workspace is never included.
   - Priority is a hard lane. A higher Tavily or paper score cannot replace a video passage. Video passages are listed first. Outside text can appear only in the external panel.
4. Rerank inside each lane with the configured chat model, listwise or pointwise. Keep the top 4 video passages. Keep the top 3 outside sources only when the checkbox is on. If the model call fails, fall back to lexical overlap inside the same lane.
5. Decision, from the lanes:
   - Checkbox off and the best video score meets the threshold: `lesson_only`. `external` is empty.
   - Checkbox off and the best video score is below the threshold: `abstain`. One lesson section says the video does not cover the question. `external` is empty.
   - Checkbox on, video meets the threshold, and lane B has kept sources: `blend`. Lesson panel uses video passages. External panel uses the kept outside sources. Video claims and outside claims stay in their own panels.
   - Checkbox on, video is below the threshold, and lane B has kept sources: `blend`. The lesson panel says the video does not cover the question. The external panel answers from the kept sources only.
   - Checkbox on and lane B is empty: `lesson_only` when the video meets the threshold, otherwise `abstain`.
6. Pass only the kept passages into the existing JSON prompt, video block first, each block labeled with `evidence_origin`. Store `decision` and the kept ids with their origins in `content_json`. Do not show a raw score.
7. Thresholds live in one module, each with a one-line comment. An unrelated question with search off abstains in a unit test.
8. If the session-1 trim path is present, deleting a lesson also deletes its `external_evidence` rows and both origins of its Qdrant points for that workspace and video. Do not change the limit numbers.

## Out of scope
A reviewer model, LLM-as-judge datasets, changing the history-limit default, UI layout changes beyond the existing abstain sentence in the lesson panel.

## Acceptance
- An unrelated question with search off abstains and does not invent a lesson section or attach a paper.
- A matching video passage is sent and the unrelated video passages are dropped.
- Search off does not retrieve stored `external_search` points from this same thread.
- Search on returns a video block and an external block. The video block does not contain outside snippets. A higher outside score does not remove a video passage.
- A second thread cannot read the first thread’s outside points.
- Reindexing the same segment does not create a second Qdrant point.
- Fake-model tests cover the decision table, both filters, and the lexical fallback. A live Gemini call is not required.

## Tests
Unit tests for the decision table, the origin filter, lexical fallback, and idempotent upsert. One route test with a fake reranker. Run targeted tests, lint, and typecheck.

## Done means
Reply with implemented, files changed, tests and results, one manual check, risks, and a suggested commit message. Do not commit, push, or start the next session unless the operator asks. Then stop.
