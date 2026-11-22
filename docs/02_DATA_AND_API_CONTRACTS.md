# 02 — Data Model, HTTP Contracts and Evidence Schema
> **Data stores:** Neon (Postgres) is the source of truth. Qdrant Cloud holds the derived vector index only.


## 1. PostgreSQL entities (initial MVP)

All IDs are UUIDs; all UTC instants use `timestamptz`; `created_at`/`updated_at` required where meaningful. Migration is authoritative, not an ORM auto-create on every app boot.

| Table | Principal fields | Constraints / notes |
| --- | --- | --- |
| `users` | id, email, password_hash, status, email_verified_at, created_at | unique case-normalized email; Argon2id; no plaintext passwords |
| `workspaces` | id, name, owner_user_id, created_at | private workspace by default |
| `workspace_memberships` | user_id, workspace_id, role | unique pair; MVP role `owner`/`member` |
| `sessions` | id, user_id, refresh_token_hash, expires_at, revoked_at, device_info | hashed refresh token, rotation, audit |
| `videos` | id, workspace_id, youtube_video_id, title, channel_title, duration_seconds, source_url, status, metadata_json | unique `(workspace_id,youtube_video_id)`; metadata may be nullable |
| `playlists` | id, workspace_id, youtube_playlist_id, title, status, total_items, indexed_at | unique `(workspace_id,youtube_playlist_id)` |
| `playlist_items` | id, playlist_id, video_id nullable, playlist_position, youtube_video_id, state | preserve order and unavailable IDs; unique `(playlist_id,playlist_position)` |
| `source_assets` | id, video_id, workspace_id, source_kind, storage_key, content_hash, rights_attested_at, uploaded_by, timecode_quality, source_revision | no publicly accessible blob path; typed source provenance |
| `transcript_segments` | id, asset_id, video_id, workspace_id, ordinal, text, start_ms nullable, end_ms nullable, speaker nullable, content_hash | check start <= end when nonnull; no fake timecodes |
| `chapters` | id, video_id, workspace_id, source_revision, title, start_segment_id, end_segment_id, topic_json | chapter title/source mapping |
| `summaries` | id, workspace_id, scope_kind, scope_id, summary_kind, revision, content_json, coverage_json, provider_run_id | unique by version + scope + kind |
| `concepts` | id, workspace_id, canonical_name, description | optional in MVP |
| `concept_edges` | src_concept_id, dst_concept_id, relation, evidence_span_id | add only later for research feature |
| `index_manifests` | id, workspace_id, video_id, embedding_profile, source_revision, qdrant_collection, chunk_count, status | tracks derived retrieval |
| `ingestion_jobs` | id, workspace_id, video_id, source_asset_id, job_type, status, stage, attempt, lease_until, idempotency_key, last_error_code, percent | unique idempotency key; bounded transition state machine |
| `outbox_events` | id, event_kind, payload_json, status, created_at, attempts | optional reliable enqueue pattern |
| `chat_threads` | id, workspace_id, scope_kind, scope_id, title, created_by | scope video/playlist/library |
| `chat_messages` | id, thread_id, workspace_id, role, content, provider_run_id, created_at | no arbitrary tool invocations |
| `message_citations` | id, message_id, segment_id, start_ms nullable, end_ms nullable | server-resolved citation IDs |
| `provider_runs` | id, workspace_id, provider, model, operation, request_hash, token_in, token_out, cost_estimate_usd, latency_ms, status, created_at | cost estimation for dashboards; never log secrets |
| `usage_limits` | workspace_id, period, jobs_used, tokens_used, estimated_spend_usd | enforce server side in transactions |
| `audit_events` | id, workspace_id, actor_user_id, action, resource_type, resource_id, metadata_json, created_at | exclude raw transcript and keys |

**Deletion:** use transaction + deletion job to remove child rows, index points, object content; treat vector and object cleanup as eventually consistent but tracked and retried. Audit records only minimal deletion metadata.

## 2. Qdrant collection design

Collection name: `learnlens_chunks_<embedding_profile_slug>_v1`; one collection per **embedding model/dimension/version profile**, not one per user or arbitrary playlist. On ingest points must contain:

```json
{
  "workspace_id": "uuid",
  "video_id": "uuid",
  "playlist_ids": ["uuid"],
  "source_asset_id": "uuid",
  "source_revision": 1,
  "segment_ids": ["uuid"],
  "chunk_id": "uuid",
  "start_ms": 120000,
  "end_ms": 171500,
  "title": "Effective communication",
  "language": "en",
  "content_hash": "sha256...",
  "embedding_profile": "gemini-embedding-001-768-v1"
}
```

`start_ms` and `end_ms` are **null** if timing is unavailable. Store only a short text preview if needed; authoritative transcript is in Postgres. Create keyword indexes on workspace_id and video_id plus filters actually used; tenant index on workspace_id when supported. Query uses `must: workspace_id` plus scope-specific video IDs derived from SQL authorization. Never accept a free-form Qdrant filter from the browser.

**Hybrid retrieval:** configure named dense vector and named lexical/sparse retrieval, merge with Qdrant query API RRF. Use documented Qdrant-supported BM25 path for the pinned version; avoid silently assuming sparse and BM25 are identical. Record retrieved candidate IDs and scores without raw content in routine telemetry. At MVP, top_k=8-12 candidates, bounded context and optional rerank only after benchmarking.

## 3. Stable API convention

Base path: `/api/v1`. JSON property names `snake_case`. Errors use:

```json
{"error":{"code":"SOURCE_TRANSCRIPT_REQUIRED","message":"Upload a permitted transcript to summarize this video.","request_id":"uuid","details":{}}}
```

Do not include stack traces or provider error bodies in public errors. All protected endpoints require authenticated session and `workspace_id` derived from it, not caller supplied. CSRF token for state-changing cookie-auth requests. `Idempotency-Key` for import endpoints. Use cursor-based pagination for lists; explicit limit maxima.

## 4. Core endpoints

| Method | URL | Body / query | Response |
| --- | --- | --- | --- |
| POST | `/auth/register` | email, password, optional name | account session / verification state |
| POST | `/auth/login` | email, password | secure session cookies |
| POST | `/auth/refresh` | refresh session | rotated session |
| POST | `/auth/logout` | CSRF-protected | revoke session |
| GET | `/me` | none | current identity and workspace |
| POST | `/videos/import` | `{youtube_url}` | metadata record + source status |
| GET | `/videos` | cursor, limit, status | paginated owned videos |
| GET | `/videos/{video_id}` | none | metadata, processing status and coverage |
| POST | `/videos/{video_id}/transcripts` | multipart upload, rights attestation, source kind | `202` with job ID |
| GET | `/videos/{video_id}/chapters` | none | list of chapter refs |
| GET | `/videos/{video_id}/summaries` | kind | summaries with evidence IDs |
| POST | `/playlists/import` | `{youtube_url}` | playlist record and item statuses |
| GET | `/playlists/{playlist_id}` | none | ordered items and coverage |
| POST | `/playlists/{playlist_id}/synthesize` | no content | `202` background job |
| GET | `/playlists/{playlist_id}/summary` | none | partial/complete coverage-aware summary |
| GET | `/jobs/{job_id}` | none | status/stage/percent/errors |
| POST | `/chat/threads` | scope video/playlist/library | new thread |
| POST | `/chat/threads/{thread_id}/messages` | question, explanation_mode | validated answer+citation list |
| GET | `/chat/threads/{thread_id}/messages` | cursor | thread messages |
| GET | `/settings/providers` | none | configured allowed provider names and models, no keys |
| PUT | `/settings/providers` | chosen text provider/model & embedding profile | selected provider; reindex warning if embedding changes |
| GET | `/usage` | period | counts, estimated cost, quotas |
| DELETE | `/videos/{video_id}` | CSRF and ownership | scheduled deletion |
| POST | `/tutor/decks` | video_id, optional presentation_language (`en`\|`ta`) | source-grounded flashcard/quiz deck with citations |
| GET | `/tutor/decks` | optional video_id | user-owned decks in workspace |
| GET | `/tutor/decks/{deck_id}` | none | deck + items + evidence + concept edges |
| DELETE | `/tutor/decks/{deck_id}` | CSRF | delete user-owned generated practice content |
| POST | `/tutor/decks/{deck_id}/attempts` | item_id, selected_choice_index / response_text | graded attempt; evidence resolved from DB |
| GET | `/tutor/review` | limit | due spaced-review items for current user |
| POST | `/tutor/review/{item_id}` | grade (`again`\|`hard`\|`good`\|`easy`) | advance SM-2-lite schedule |
| GET | `/tutor/progress` | none | per-user practice counts (no efficacy claims) |
| GET | `/tutor/concepts` | optional video_id | concept nodes + prerequisite edges (Postgres) |
| GET/PUT | `/tutor/preferences` | presentation_language | en/ta presentation; evidence stays original language |

Authentication and CRUD endpoints require further OpenAPI-generated documentation during implementation. Use explicit 400/401/403/404/409/413/422/429/503 statuses.

## 5. Structured response schemas

**Video chapter:**

```json
{
  "chapter_title": "Active listening",
  "start_segment_id": "uuid",
  "end_segment_id": "uuid",
  "key_claims": [{"claim":"Listening requires attention and clarification.","evidence_segment_ids":["uuid"]}],
  "examples": [{"text":"In a code review, restate requirements.","origin":"ai_generated_illustration"}]
}
```

**Grounded AI answer (provider-output contract):**

```json
{
  "answer":"The instructor recommends asking clarifying questions [1].",
  "claims":[{"text":"Ask clarifying questions.","citation_segment_ids":["uuid"]}],
  "unsupported": false,
  "confidence_label":"supported"
}
```

Server rehydrates each returned segment ID **only from the retrieved authorized evidence packet**, discards unsupported IDs, validates evidence scope and source timecodes. A claim with no supporting evidence is removed, qualified, or causes a supported-evidence refusal. Render source reference blocks from the server, not model-generated URLs. `confidence_label` is application-assessed (evidence quality + validator) rather than blindly trusting the model. An answer can have unlabeled conversational filler, but meaningful source claims need citations.

**Citation response to UI:**

```json
{
  "citation_id":"c_01",
  "video_id":"uuid",
  "video_title":"Communication foundations",
  "segment_id":"uuid",
  "snippet":"...",
  "start_ms":123000,
  "end_ms":142000,
  "youtube_url":"https://www.youtube.com/watch?v=VALID_ID&t=123s",
  "timing_verified":true
}
```

When `timing_verified=false`, `start_ms`, `end_ms`, and timestamped URL must be `null`; the client links only to source/video without claiming a jump location.

## 6. Versioning rules

Any change to segmentation strategy increments `processing_version`; any change to embedding model or dimensions creates a new `embedding_profile` and collection; model prompts have `prompt_version`. Existing content may be reprocessed asynchronously with status and rollback strategy. Store source hash and model/provider version in manifests.

## 7. Operator note — history, threads, origins, and the lesson cache

`workspaces.learning_history_limit` defaults to 10 and must stay between 1 and 100. Settings reads and writes that number. Saving a smaller limit trims that workspace immediately. Recent Learning and My Library both list the lessons that remain, newest `last_opened_at` first.

Each saved lesson has one chat thread for its workspace and video (`chat_threads.scope_kind = video`, `scope_id` = the lesson id). The thread, its messages, and its evidence belong to that workspace. Another workspace cannot open the list or the lesson.

Two evidence origins share the lesson's `thread_id`. `video_transcript` / `gemini_youtube` rows are `transcript_segments`. `external_search` rows are `external_evidence` with provider `tavily`, `semantic_scholar`, or `openalex`. Qdrant points are derived and carry `workspace_id`, `video_id`, `thread_id`, `evidence_origin`, `evidence_provider`, and `content_hash`. The live checkbox filters retrieval: off reads `video_transcript` only; on reads both lanes and keeps the video lane first.

Trimming a lesson deletes, for that workspace and video, the lesson, its source asset, its transcript segments, its `external_evidence` rows, its chat thread and messages, and both origins of its Qdrant points.

Redis may cache the lesson body only when `LESSON_BODY_CACHE_ENABLED` is on (off by default, including tests) and `REDIS_URL` answers. The key is `ll:lesson-body:{workspace_id}:{video_id}:{content_hash}` and expires after 10 minutes. The value is summary, key points, and transcript segments. It does not store `external_evidence` snippets or Qdrant hits. A trim, a replaced lesson, or a segment change deletes that key. If Redis is down, the read uses Neon and continues. One answer log line records ids, the decision, review status, whether search was on, kept passage counts, and token counts when the provider returned them. It does not record transcript text, snippets, URL queries, or source titles.
