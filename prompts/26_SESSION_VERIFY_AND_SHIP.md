# Session 8 — Verify live and ship session 7

**New Cursor Agent chat. Model: Grok 4.7 high and fast.** Paste only this session. Prerequisite: session 7 (`25_SESSION_LEARNER_CONTROLS.md`) is implemented in the working tree on `dev` and not yet committed.

## Purpose
Everything from session 7 and its follow-up fixes passes offline with fake providers, but none of it is committed and three behaviours have never run against real Gemini, Tavily, Neon, or Qdrant. Prove they work live, then commit the work as three clean commits, push `dev`, watch CI, and merge to `main`.

This session writes no new features. If a live check fails, stop and report; do not patch around it in this session.

## What is in the working tree
Three groups of work, each staged as whole files (no hunk-level staging is needed):

1. **Learner controls (session 7 + validation).** Pin and Remove for saved lessons, header title search, the signed-in row with Sign out / Sign in again, Home and Videos cleanup, hidden empty Chapters tab, API-mode pin fixes, and their tests.
2. **Search-on answers.** The reviewer no longer withholds answers for wording shared with a paper (`origin_mix` now needs a copied 6-word run with 3+ content words). Answers store `video_covered`, and the web panel is labelled "From web search · not from the video" with a coverage note. A subject gate drops web results on a *different* subject from the video and keeps related ones. The answer log line gains `review_reasons` and `dropped_off_subject` (codes and counts only).
3. **CI and contract notes.** A Postgres migration job, a learner-controls guardrail step, subject-gate tests in CI, and `docs/02_DATA_AND_API_CONTRACTS.md` notes.

## Read first
`AGENTS.md`, `prompts/25_SESSION_LEARNER_CONTROLS.md`, `docs/02_DATA_AND_API_CONTRACTS.md` §7, `.github/workflows/ci.yml`, `apps/api/app/retrieval/subject_gate.py`, `apps/api/app/services/session_review.py`.

## Do only this

### 1. Offline gate (must be green before anything else)
From the repo root: `make lint`, `make typecheck`, `make test`, `make eval`, `make guardrails-harness`, and `npm run build --workspace=@learnlens/web`. Record pass counts. If any fail, stop and report.

### 2. Apply the migration (ask first)
Revision `20261123_0013` adds `videos.pinned` (boolean, not null, default false). `make migrate` applies it to the Neon database in `.env`. **Ask the operator before running it**, and say which database host it will touch (host only, never the URL or password). Do not run `make migrate-down`.

### 3. Live checks
Start the API with `make dev` and the web app with `npm run dev --workspace=@learnlens/web`. Use real keys from `.env`; do not print them. For each check, write down what you saw and the matching `answer_usage` log line fields (`decision`, `review_status`, `review_reasons`, `video_covered` from the stored answer, `kept_outside_passages`, `dropped_off_subject`). Do not paste transcript text, snippets, or URLs into the report.

- **A. Search-on, related topic.** Save a lesson from a public video about the Transformer paper ("Attention Is All You Need" or similar). With web search on, ask "What is the issue with current RNNs?". Expect: an answer (not "The reviewer withheld this answer"), a web panel labelled "From web search · not from the video", and a coverage note that says either the video covers part of it or it is not covered.
- **B. Search-on, different subject.** Save a lesson from a public video about electrical power transformers. With web search on, ask "What is a transformer?". Expect: the lesson answer from the video and, if search returned only ML papers, the note "Web results were about a different subject than this video, so none are shown." with `dropped_off_subject` ≥ 1. If search happened to return electrical results, record that they were kept and note it.
- **C. Search off.** Ask any question on lesson A with search off. Expect an answer with no web panel and `review_status` of `accepted` or `regenerated`.
- **D. Pin and trim.** Save three lessons. Pin the middle one. In Settings set the limit to 1. Expect Recent Learning to show the pinned lesson and the newest. Unpin it, then set the limit to 1 again: it is removed.
- **E. Remove.** Remove a lesson from its page. Confirm the dialog text mentions the lesson, its notes, and its Ask AI thread. Expect a return to `/videos` and the lesson gone from My Library and Recent Learning.
- **F. Sign out.** Click Sign out. Refresh Recent Learning: it must not show lessons and the top bar says Signed out. Click Sign in again: the email and workspace name return.
- **G. Header search.** Type a saved lesson's title in the top bar and press Enter. Expect `/videos?q=<title>` with that lesson listed.

If A is still withheld, report the `review_reasons` codes and stop. Do not change the reviewer in this session; that becomes its own session.

### 4. Commit as three commits on `dev`
Use the repo's configured git user only. **No `Co-Authored-By` trailer or any assistant attribution.** Stage whole files with `git add <paths>`; check `git status` after each commit.

**Commit 1 — `feat: let learners pin, remove, and search saved lessons`**
```
apps/api/alembic/versions/20261123_0013_video_pinned.py
apps/api/app/api/v1/learning_history.py
apps/api/app/api/v1/schemas.py
apps/api/app/api/v1/videos.py
apps/api/app/db/models/library.py
apps/api/app/services/lesson_history.py
apps/api/tests/test_migrations.py
apps/api/tests/test_learner_controls.py
apps/api/tests/test_learner_controls_validation.py
apps/web/app/api/auth/logout/route.ts
apps/web/app/api/auth/sign-in/route.ts
apps/web/app/api/learning-history/[videoId]/route.ts
apps/web/app/api/learning-history/[videoId]/pin/route.ts
apps/web/app/api/me/route.ts
apps/web/app/library/page.tsx
apps/web/app/playlists/page.tsx
apps/web/app/videos/page.tsx
apps/web/components/lesson/chapter-timeline.tsx
apps/web/components/lesson/lesson-reader.tsx
apps/web/components/library/dashboard-home.tsx
apps/web/components/library/lesson-controls.tsx
apps/web/components/library/library-browser.tsx
apps/web/components/library/library-toolbar.tsx
apps/web/components/library/video-detail.tsx
apps/web/components/recent/recent-learning.tsx
apps/web/components/settings/learning-history-setting.tsx
apps/web/components/shell/account-status.tsx
apps/web/components/shell/app-topbar.tsx
apps/web/lib/library/client.ts
apps/web/lib/library/search-href.ts
apps/web/lib/library/types.ts
apps/web/lib/server/learning-api.ts
apps/web/tests/dashboard-home.test.tsx
apps/web/tests/header-search.test.tsx
apps/web/tests/learner-controls-proxy.test.ts
apps/web/tests/lesson-controls.test.tsx
apps/web/tests/lesson-reader-chapters.test.tsx
apps/web/tests/library-url-query.test.tsx
apps/web/tests/signed-out.test.ts
apps/web/tests/video-detail-gemini.test.tsx
prompts/25_SESSION_LEARNER_CONTROLS.md
```
Body: one short paragraph — pinned lessons survive trim; Remove reuses the trim delete sequence; header search filters `/videos` by title; Sign out sets `ll_signed_out` so the local auto-login stops; Home and Gemini lesson pages drop transcript-upload chrome; the pin body accepts only JSON booleans.

Before commit 2, prove commit 1 stands alone: `git stash push --include-untracked`, run `make lint`, `make typecheck`, `make test`, then `git stash pop`. If anything fails with only commit 1 applied, stop and report which file is missing from the list.

**Commit 2 — `fix: keep search-on answers and drop off-subject web results`**
```
apps/api/app/api/v1/lesson_chat.py
apps/api/app/retrieval/subject_gate.py
apps/api/app/services/answer_usage.py
apps/api/app/services/session_chat.py
apps/api/app/services/session_evidence.py
apps/api/app/services/session_review.py
apps/api/tests/test_session_production_fit.py
apps/api/tests/test_session_review.py
apps/api/tests/test_subject_gate.py
apps/web/components/lesson/answer-view.tsx
apps/web/components/lesson/chat-panel.tsx
apps/web/lib/lesson/answer.ts
apps/web/tests/answer-view.test.tsx
apps/web/tests/chat-panel.test.tsx
```
Body: the reviewer's `origin_mix` floor now needs a copied distinctive run, not any shared 4-word phrase; answers store `video_covered` and the web panel says how far the video covers the question; a subject gate drops only web results on a different subject; the log line adds reason codes and a dropped count.

**Commit 3 — `ci: run learner-control, subject-gate, and Postgres migration checks`**
```
.github/workflows/ci.yml
docs/02_DATA_AND_API_CONTRACTS.md
prompts/26_SESSION_VERIFY_AND_SHIP.md
prompts/27_SESSION_GEMINI_ROUTE_AUTH.md
```
After commit 3, `git status` must be clean. If any file is left over, stop and report it rather than guessing which commit it belongs to.

### 5. Push and watch CI
`git push origin dev`. Watch the run with `gh run watch` (or `gh run list --branch dev`). All jobs must pass, including the new `migrations-postgres` job, whose first run is this one. If a job fails, report the failing step and its log excerpt and stop. Do not merge on red.

### 6. Merge to `main` (only when CI is green)
```
git checkout main
git pull --ff-only origin main
git merge --no-ff dev -m "Merge branch 'dev'"
git push origin main
git checkout dev
```

## Out of scope
New features, reviewer or gate tuning, the Gemini route auth fix (session 9), pin caps, Qdrant delete retries, mobile search, dependency upgrades, `ruff format` across the repo, force-push, rewriting history, deleting branches.

## Acceptance
- The offline gate and the web build pass, with counts recorded.
- `videos.pinned` exists in Neon (operator-approved `make migrate`).
- Live checks A–G each have an observed result. A shows an answer with the coverage note, not a withheld message.
- Three commits on `dev` with the exact titles above, no assistant attribution, and a clean `git status` afterwards.
- CI is green on `dev`, including `migrations-postgres`, and `main` has the `Merge branch 'dev'` merge commit.

## Done means
Reply with: offline gate results; the migration host and outcome; a table of live checks A–G (expected, observed, log fields); the three commit hashes; the CI run link and job results; the merge commit hash. List anything that failed or was skipped and why. Then stop.
