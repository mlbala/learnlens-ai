# Session 9 — Lock the Gemini routes behind a session

**New Cursor Agent chat. Model: Grok 4.7 high and fast.** Paste only this session. Prerequisite: session 8 is merged to `main`, and `dev` is synced from `main`.

## Purpose
Three web routes spend the server's paid keys without checking who is calling:

- `POST /api/gemini-lesson` (`apps/web/app/api/gemini-lesson/route.ts`) asks Gemini to watch a YouTube video. It has no session check.
- `POST /api/gemini-ask` (`apps/web/app/api/gemini-ask/route.ts`) asks Gemini a lesson question. It has no session check.
- `POST /api/lesson-chat` (`apps/web/app/api/lesson-chat/route.ts`) runs `buildSearchPlan` (a Gemini call) and `searchTopicSources` (Tavily, Semantic Scholar, OpenAlex) **before** its first `proxyLearningApi` call. A signed-out caller is rejected only after the paid calls have already run.

After this session, no Gemini or search-provider call happens unless the FastAPI API has confirmed a signed-in session for that request.

## Locked contract
- The web server never trusts cookie presence alone. A session counts only when `GET /api/v1/me` returns 200 for the request's cookies, after at most one refresh.
- Signed out means 401 with `{ "error": { "code": "AUTH_REQUIRED", "message": "Sign in again to build or ask about lessons." } }`. Nothing paid is called.
- If the API cannot be reached to verify the session, return 503 `API_UNAVAILABLE` and call nothing paid. Fail closed.
- `ll_signed_out=1` keeps working exactly as in session 7: no automatic local login while it is set.
- The browser never receives provider keys. No new environment variables. No API (FastAPI) changes.

## Current state you must preserve
- `ensureWorkspace` and `proxyLearningApi` in `apps/web/lib/server/learning-api.ts` keep their behaviour: the local learner (`WEB_WORKSPACE_EMAIL`) is logged in on first use in development, and is not logged in while `ll_signed_out=1` is set, or in production without `WEB_WORKSPACE_PASSWORD`.
- `/api/youtube-oembed` stays public. It calls YouTube's free oEmbed endpoint with no key.
- The search plan, subject gate, reviewer, and coverage note behave as they do now for signed-in users.
- Existing web tests stay green, including `tests/signed-out.test.ts` and `tests/learner-controls-proxy.test.ts`.

## Read first
`AGENTS.md`, `apps/web/lib/server/learning-api.ts`, `apps/web/app/api/gemini-lesson/route.ts`, `apps/web/app/api/gemini-ask/route.ts`, `apps/web/app/api/lesson-chat/route.ts`, `apps/web/lib/lesson/gemini-ask.ts`, `apps/web/lib/search/search-plan.ts`, `apps/web/lib/search/topic-sources.ts`, `apps/web/lib/library/client.ts` (the `/api/gemini-lesson` caller), `apps/web/lib/lesson/client.ts` (the `/api/gemini-ask` and `/api/lesson-chat` callers), `apps/web/tests/signed-out.test.ts`.

## Implement only this
1. **One session check.** In `apps/web/lib/server/learning-api.ts`, add and export:
   ```ts
   requireLearningSession(request: Request): Promise<
     | { ok: true; jar: CookieJar; setCookies: string[] }
     | { ok: false; response: NextResponse }
   >
   ```
   It parses the request cookies, runs `ensureWorkspace(jar)`, then calls `GET /api/v1/me` with the jar's cookies. On 401 it tries `refreshSession` once and calls `/me` again. It returns `ok: true` only on a 200 from `/me`. Signed out, a missing `ll_access`, or a forged or expired token gives the 401 above. A network error or 5xx from the API gives the 503. Collect every `Set-Cookie` line from login or refresh in `setCookies`. Reuse the existing private helpers; do not copy them.
2. **Let later proxy calls reuse the verified session.** Add an optional `session?: { jar: CookieJar; setCookies: string[] }` to `proxyLearningApi`'s options. When it is given, use that jar instead of re-reading the request's cookie header, and skip `ensureWorkspace`. This matters because a refresh rotates the refresh token: re-reading the stale request cookies would send an old token. Existing callers that do not pass it keep their current behaviour.
3. **Gate the three routes at the very top**, before reading the body, building prompts, or calling any provider:
   - `gemini-lesson`: `const session = await requireLearningSession(request); if (!session.ok) return session.response;`. Then do the existing work and append `session.setCookies` to the final response, success or error.
   - `gemini-ask`: same.
   - `lesson-chat`: same check as its first statement, before `buildSearchPlan` and `searchTopicSources`. Pass `session` into every `proxyLearningApi` call in that route, and append `session.setCookies` to the response it returns.
   Keep the `GEMINI_API_KEY is not set` 503 in `gemini-lesson`, but after the session check.
4. **Clear client message.** Where `apps/web/lib/library/client.ts` calls `/api/gemini-lesson`, and where `apps/web/lib/lesson/client.ts` calls `/api/gemini-ask` and `/api/lesson-chat`, a 401 must surface the API's message ("Sign in again to build or ask about lessons.") through the existing error path, not a generic failure. Do not add a sign-in screen; the top bar already offers Sign in again.

## Out of scope
Rate limiting or per-workspace spend caps on web routes, CAPTCHA, a sign-in or registration form, new providers, changes to FastAPI, changes to the search plan, subject gate, or reviewer, `youtube-oembed`, pin caps, Qdrant delete retries, dependency upgrades.

## Acceptance
- With `ll_signed_out=1`, each of the three routes returns 401 `AUTH_REQUIRED`, and the mocked `fetch` sees no request to `generativelanguage.googleapis.com`, `api.tavily.com`, `api.semanticscholar.org`, or `api.openalex.org`.
- With a forged `ll_access` cookie, where `/api/v1/me` answers 401 and refresh fails, each route returns 401, and no Gemini or search call is made.
- With the API unreachable, each route returns 503 `API_UNAVAILABLE`, and no Gemini or search call is made.
- In production mode without `WEB_WORKSPACE_PASSWORD` and with no cookies, each route returns 401 and makes no paid call.
- With a valid session (`/me` returns 200), `gemini-lesson` and `gemini-ask` call Gemini exactly as before. `lesson-chat` calls the search plan and search only after `/me` succeeds, and its proxy calls reuse the verified jar.
- When `/me` first answers 401 and refresh succeeds, the refreshed `Set-Cookie` lines reach the browser, and the later `lesson-chat` proxy calls send the refreshed `ll_access`, not the stale one.
- Signing out in the top bar and then building a lesson or asking a question shows "Sign in again to build or ask about lessons." and makes no paid call.

## Tests
Add `apps/web/tests/gemini-route-auth.test.ts` with `// @vitest-environment node`. Import each route's `POST` and mock `fetch` by URL. Cover:
- signed out (`ll_signed_out=1`)
- forged token
- API down
- production without a password
- a valid session, for each of the three routes
- the refresh-then-reuse case for `lesson-chat`

For every rejection, assert the status, the error code, and that no request went to a Gemini or search host. Add one test for `requireLearningSession` on its own. Keep the existing `signed-out` and `learner-controls-proxy` tests passing.

Add `tests/gemini-route-auth.test.ts` to the "Web session + learner control safety tests" step in `.github/workflows/ci.yml`.

Run `npm run test --workspace=@learnlens/web`, `make lint`, `make typecheck`, `npm run build --workspace=@learnlens/web`, and `make test`.

## Done means
Reply with:
- what you implemented
- the files changed
- the test results with counts
- one manual check: with `make dev` and the web dev server running, click Sign out, try to add a video and ask a question, and confirm the message and that the server log shows no Gemini or search call
- risks
- a suggested commit message

Commit on `dev` only if the operator asks. Use the repo's git user with no assistant attribution, then follow the `AGENTS.md` push-and-merge flow. Then stop.
