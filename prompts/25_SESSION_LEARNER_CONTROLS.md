# Session 7 — Learner controls

**New Cursor Agent chat. Model: Grok 4.7 high and fast.** Paste only this session. Prerequisite: session 6 is accepted.

## Purpose
A learner can find a saved lesson from the header, remove or pin it, see who is signed in, and stop seeing transcript-upload chrome on a Gemini lesson. Chapters stay hidden when the lesson has no verified times.

## Locked evidence contract
Neon is the system of record. Do not invent `start_ms` or `end_ms`. Gemini lesson passages stay `source_kind = gemini_youtube` with null timestamps.

Removing one lesson deletes, for that workspace and video only: the video row, its source asset, its transcript segments, its chapters, its `external_evidence` rows, its chat thread and messages, its citations, and both origins of its Qdrant points. Clear that lesson’s Redis body key. Another workspace is untouched.

Do not add MongoDB. Do not download the YouTube file. Do not change the embedding dimension. Do not build a practice deck.

## Current state you must preserve
- Home already says “Paste a public YouTube link.” Ask AI stays beside the player. Study notes stay under the player. Answers still render through `AnswerView`.
- `learning_history_limit` stays 1–100, default 10. Trim still deletes the oldest unpinned Gemini lessons and everything in the evidence contract above. The delete sequence lives in `LessonHistoryService.trim` in `apps/api/app/services/lesson_history.py`.
- `VideoDeletionService` in `apps/api/app/services/video_deletion.py` does not remove chat threads or `external_evidence`. Do not use it for this remove action.
- Gemini bundles return `chapters: []` from `FixtureLessonClient` in `apps/web/lib/lesson/client.ts`. `LessonReader` still renders a Chapters tab.
- Header search in `apps/web/components/shell/app-topbar.tsx` is disabled. Title search already works inside `LibraryBrowser` through `useVideosInfinite({ q })`.
- The web app signs in `learner@example.com` (or `WEB_WORKSPACE_EMAIL`) inside `ensureWorkspace` in `apps/web/lib/server/learning-api.ts`. There is no sign-in screen. `GET /api/v1/me` returns `user.email`, `user.display_name`, and `workspace.name`.
- Playlists stay. A video that is not a Gemini lesson may still offer a permitted transcript upload.

## Read first
`AGENTS.md`, `docs/02_DATA_AND_API_CONTRACTS.md`, `apps/api/app/services/lesson_history.py`, `apps/api/app/api/v1/learning_history.py`, `apps/api/app/db/models/library.py`, `apps/web/components/lesson/lesson-reader.tsx`, `apps/web/components/shell/app-topbar.tsx`, `apps/web/components/library/dashboard-home.tsx`, `apps/web/components/library/library-browser.tsx`, `apps/web/components/library/video-detail.tsx`, `apps/web/lib/server/learning-api.ts`.

## Implement only this
1. **Chapters.** In `LessonReader`, omit the Chapters tab when `chapters` is empty. If a chapter exists and `start_ms` is null, show the title and leave seek disabled. Do not generate chapters and do not fill times.
2. **Pin.** Add `videos.pinned`, boolean, not null, default false. Alembic revision revises `20261122_0012`. `trim` counts only unpinned Gemini lessons toward `learning_history_limit`. Pinned lessons stay, and they still show in My Library and Recent Learning. Unpinning lets the next trim drop the oldest unpinned lessons with the existing delete sequence.
3. **Remove.** Add `LessonHistoryService.remove_lesson` by reusing the per-video deletes inside `trim`. `DELETE /api/v1/learning-history/{video_id}` requires CSRF and returns 404 `LESSON_NOT_IN_WORKSPACE` for another workspace. `PUT /api/v1/learning-history/{video_id}/pin` with `{ "pinned": true | false }` requires CSRF. Proxy both through the existing learning-history web routes. On the lesson page, each library row, and each Recent Learning row, add Remove and Pin. Remove asks for confirmation and says it deletes the lesson, its notes, and its Ask AI thread. Extend the Settings sentence so it says pinned lessons are kept when the limit drops the oldest.
4. **Header search.** Enable the top-bar search. Submitting it opens `/videos?q=`. `LibraryBrowser` reads `q` from the URL on load and passes it to the existing title filter. An empty submit clears `q`. Do not search transcript text, chat, or outside snippets.
5. **Signed-in row.** The top bar shows the email and workspace name from `GET /api/v1/me`, proxied at `apps/web/app/api/me/route.ts`. Sign out calls `POST /api/v1/auth/logout`, clears `ll_access`, `ll_refresh`, and `ll_csrf`, and sets `ll_signed_out=1`. While that cookie is set, `ensureWorkspace` must not log the local user back in. The top bar then says Signed out and offers Sign in again, which clears `ll_signed_out` and uses the existing local login. No registration form, no password field, no second workspace.
6. **One product story.** On Home, remove the Pending transcripts card and the Jobs needing attention section. Keep Lessons saved and Playlists. On the Videos page, hide the Needs transcript status filter. On a Gemini lesson (`transcript_access` and not `fixture_data`), do not render `TranscriptImportDialog` or the sentence “Owner-authorized caption download is not configured.” Keep that upload empty state only for a video that has no transcript. On the Playlists page, say this list is official playlist metadata and permitted transcripts, separate from a pasted video lesson.

## Out of scope
Practice decks, quizzes, concept graphs, a model picker, live vendor prices, owner-caption download, organizations, a public registration form, YouTube download, new evidence origins.

## Acceptance
- A Gemini lesson with no chapters does not show a Chapters tab, and no timestamp is written.
- Pinning a lesson and setting the limit to 1 keeps that lesson and drops the oldest unpinned one, including its segments, external rows, and chat thread. Another workspace cannot remove or pin it.
- Header search for a saved title opens `/videos?q=` with that title matched. Transcript words are not a search field.
- After Sign out, a following learning-history call does not recreate the session until Sign in again. The top bar shows the email from `/api/v1/me` while signed in.
- Home does not render “Pending transcripts” or “Jobs needing attention.” A Gemini lesson page does not offer a transcript upload.

## Tests
API tests for pin surviving trim, unpin then trim deleting that lesson, remove clearing segments and the thread, and a second workspace receiving 404. One web test that the Chapters tab is absent when `chapters` is empty. One web test that header search writes `q` onto `/videos`. One web test that `ll_signed_out` blocks `ensureWorkspace`. One web test that Home omits the pending-transcript copy. Run targeted pytest and `npm run test --workspace=@learnlens/web` for the new files, plus `make lint` and `make typecheck`. If `make test` is too broad, say what you did not run.

## Done means
Reply with implemented, files changed, tests and results, one manual check, risks, and a suggested commit message. Do not commit, push, or start another session unless the operator asks. Then stop.
