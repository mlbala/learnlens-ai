# Session 5 — LLM-as-judge scores, offline first

**New Cursor Agent chat. Model: Grok 4.7 high and fast.** Paste only this session. Prerequisite: session 4 is accepted.

## Purpose
Score whether an answer stays on the question and on the origin it was allowed to use. Calibrate the judge on the golden set before any number is shown to a learner.

## Locked evidence contract
The judge sees the same split the reviewer saw:

- Lesson panel, scored only against the kept `video_transcript` passages.
- External panel, scored only against the kept `external_search` passages, and only when the recorded decision is `blend` and that turn’s `external_search_enabled` is true.
- When the checkbox is off, the allowed set is the video passages of this `thread_id` only. A claim that is true only of a stored Tavily or paper hit fails faithfulness even if an older turn in the thread used that hit.
- `fabricated_timestamp` is true when the answer states a time the video rows do not store.

The judge does not replace the reviewer. It does not retrieve, search, or change the draft the learner sees.

## Current state you must preserve
- Offline eval already exists: `apps/api/app/eval/`, `fixtures/golden/`, `make eval`. Dataset 1.1.0. Hard gates include citation validity, leaked tenant count 0, and fabricated timestamps 0. Do not weaken those gates.
- CI job `eval-suite` must not become a requirement of `docker-build`. `docker-build` needs stay `quality` and `security-guardrails` only.
- Live answers already carry `decision`, `review_status`, and kept ids with origins. Judge output is an extra record.
- Fake providers are the default. A judge test must not call a paid API.

## Read first
`AGENTS.md`, `docs/05_RAG_SUMMARIZATION_AND_EVAL.md`, `fixtures/golden/targets.json`, `apps/api/app/eval/suite.py`, `.github/workflows/ci.yml`.

## Implement only this
1. Add a judge rubric with three scores from 0 to 1 and one boolean:
   - `relevance`: the answer addresses the question.
   - `faithfulness`: every lesson claim is supported by a kept `video_transcript` passage, and every external claim is supported by a kept `external_search` passage for this thread.
   - `source_precision`: every listed source URL is a kept `external_search` URL, and a `lesson_only` or `abstain` answer lists none.
   - `fabricated_timestamp`: true or false.
2. The judge sees the question, the live checkbox, the decision, the draft the learner would see, and the allowed passages with origin and id. It does not see the tutor system prompt and it does not get tools.
3. Extend the offline suite with at least 4 cases:
   - a follow-up that depends on the previous lesson panel
   - an abstain with search off
   - a blend whose external sentences stay on the kept paper or doc URLs
   - a search-off answer, after an earlier blend in the same thread, that repeats a paper-only claim
   - one answer that invents a timestamp
   The invented-timestamp case and the paper-only-after-disable case fail the suite. Fake the judge in unit tests. The suite fixture judge must be swappable so CI stays offline.
4. Record scores on the assistant message only when a real judge runs. Do not render a numeric score in the lesson UI. Operators can read the stored JSON.
5. Fail `make eval` when `fabricated_timestamp` is true or when leaked-tenant behavior regresses. Do not add a new hard gate on the soft relevance number until `targets.json` records an expected band and the test shows the actual fixture-judge value.

## Out of scope
Showing scores in the product UI, a new model vendor, changing docker-build dependencies, history limits, retrieval changes.

## Acceptance
- `make eval` still passes offline on the existing hard gates.
- The invented-timestamp case fails.
- The case that repeats a paper claim after search is turned off fails faithfulness.
- The follow-up case is scored against the prior lesson panel, not against omitted external text.
- `docker-build` job needs are unchanged.
- Learner UI has no new score badge.

## Tests
Eval tests for the new cases and for “score is not required in the web bundle”. Run `make eval` or the eval unit tests if the full suite cannot run, and say which.

## Done means
Reply with implemented, files changed, tests and results, one manual check, risks, and a suggested commit message. Do not commit, push, or start the next session unless the operator asks. Then stop.
