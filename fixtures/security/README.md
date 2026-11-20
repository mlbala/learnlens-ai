# Security fixtures

Synthetic adversarial payloads for phase 13 offline tests.
Not real YouTube content. Marked as fixture data only.

| Path | Purpose |
| --- | --- |
| `injection_corpus.jsonl` | Prompt-injection / XSS / exfil phrases for matrix + harness (`channel`, `expected_verdict`) |
| `../transcripts/malicious_prompt.vtt` | Caption-shaped injection sample used as untrusted evidence |

Offline harness: `make guardrails-harness` (`python -m app.guardrails_harness`) scans this corpus and checks the bounded output regeneration loop.
