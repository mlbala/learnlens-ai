# Session 4 — Reviewer agent for the drafted answer

**New Cursor Agent chat. Model: Grok 4.7 high and fast.** Paste only this session. Prerequisite: session 3 is accepted.

## Purpose
A second model call checks the draft against the passages that retrieval actually kept. It rejects an answer that treats an outside source as the video, invents a source, or invents a timestamp.

## Locked evidence contract
Session 3 stored two origins on the same `thread_id`:

- `video_transcript` / `gemini_youtube` from `transcript_segments`
- `external_search` / `tavily` | `semantic_scholar` | `openalex` from `external_evidence`

The draft has a decision: `lesson_only`, `blend`, or `abstain`. The reviewer sees only the kept passages, each labeled with `evidence_origin` and id. Dropped passages, other threads, and tools are not included.

Allowed support:

- A sentence in the lesson panel may be supported only by a kept `video_transcript` id.
- A sentence in the external panel may be supported only by a kept `external_search` id, and only when the decision is `blend` and this turn’s checkbox was on.
- `lesson_only` and `abstain` have an empty external panel.
- `abstain` is one lesson section titled “Not answered” and does not add facts from either origin.

Do not download YouTube media. Do not invent timestamps. Do not add MongoDB.

## Current state you must preserve
- Draft answers are JSON `v: 1` from `POST /api/gemini-ask`.
- Guardrails live in `apps/api/app/core/policies/ai_guardrails.py` and `apps/api/app/core/policies/guardrail_scan.py`. Direct user injection blocks. Evidence injection is quarantined. Output block can regenerate up to `AI_GUARDRAILS_MAX_REGEN_LOOPS`. Reuse that policy. Do not build a second guardrail stack.
- Layout, answer cards, history limit, and the last-8 packing rule stay as they are.

## Read first
`AGENTS.md`, `docs/06_SECURITY_GUARDRAILS.md`, `apps/api/app/core/policies/ai_guardrails.py`, `apps/web/app/api/gemini-ask/route.ts`.

## Implement only this
1. After the draft JSON is parsed, run a reviewer call with the question, the decision, the live checkbox, the draft, and the kept passages with origin and id. The reviewer returns JSON: `accept` boolean and `reasons` using only these codes: `off_lesson`, `origin_mix`, `invented_source`, `invented_timestamp`, `injection`, `empty`.
2. `origin_mix` means the lesson panel depends on an `external_search` passage, or the external panel is present when the decision is not `blend`.
3. `invented_source` means a URL in the draft is not one of the kept `external_search` URLs. `invented_timestamp` means the draft states a time the kept video rows do not store.
4. The reviewer prompt has no tools and no web search. It must not receive passages the decision step dropped.
5. If `accept` is false, regenerate the draft once with the reason codes appended, still using only the kept passages. Review the second draft. If it still fails, store an abstain the UI already understands: one lesson section titled “Not answered”, empty `external`, empty `sources`.
6. Persist `review_status` on the assistant `content_json`: `accepted`, `regenerated`, or `withheld`. Do not show chain-of-thought or the raw reviewer JSON in the UI.
7. Use the same chat model as the draft. Skip retired Gemini ids matching `gemini-2.5`, `gemini-2.0`, and `gemini-1.`. A reviewer timeout withholds the draft. Offline tests inject a fake reviewer.

## Out of scope
Judge datasets, score badges, new layout, history-limit changes, new retrieval rules.

## Acceptance
- A lesson sentence that is true only of a kept paper is `origin_mix` and is regenerated or withheld.
- A draft that cites a URL not in the kept outside sources is rejected.
- A draft that adds a timestamp the video rows do not contain is rejected.
- Search off plus a non-empty external panel is `origin_mix`.
- An accepted draft is unchanged and still renders in `AnswerView`.
- Reviewer timeout withholds the answer rather than showing an unreviewed draft.

## Tests
Fake-reviewer tests for accept, `origin_mix`, one regenerate, withhold, and timeout. One test that the reviewer payload does not include dropped passages or the other origin when the checkbox is off. Run targeted tests, lint, and typecheck.

## Done means
Reply with implemented, files changed, tests and results, one manual check, risks, and a suggested commit message. Do not commit, push, or start the next session unless the operator asks. Then stop.
