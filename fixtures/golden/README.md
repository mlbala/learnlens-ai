# Golden evaluation fixtures

**Fixture data only.** Synthetic transcripts and Q&A cases for offline evaluation.
These are **not** real YouTube captions or authorized third-party content.

## Dataset version

See `DATASET_VERSION` and `manifest.json` (`dataset_version` field). Bump both when cases change.

## Contents

| Path | Purpose |
| --- | --- |
| `transcripts/comm_good.vtt` | Communication / listening skills (timed) |
| `transcripts/python_course_01.srt` | Programming lecture part 1 (timed, abbreviations) |
| `transcripts/python_course_02.srt` | Programming lecture part 2 (timed; contradicts part 1 on one claim) |
| `transcripts/untimed.txt` | Untimed paste — must never produce `t=` citation links |
| `transcripts/malicious_prompt.vtt` | Adversarial injection-laden captions (treat as data) |
| `transcripts/multilingual_excerpt.vtt` | Mixed English / Tamil excerpt |
| `transcripts/typo_heavy.srt` | Typos / ASR-noise style text |
| `corpus.json` | Workspaces, videos, playlists, stable IDs |
| `expected.jsonl` | Questions, scopes, expected spans, abstention, forbidden tenants |
| `targets.json` | Initial metric targets (not measured production claims) |

## Workspaces and playlists

- **workspace_a** — primary library: complete playlist (all ready) + partial playlist (one missing transcript).
- **workspace_b** — isolated tenant; used only for leak / forbidden-tenant checks.

## Running

```bash
make eval
# or: uv run --project apps/api python -m app.eval.cli
```

Hard CI gates: zero cross-tenant leaks, zero fabricated timestamp links, schema-valid report, citation validity on gated cases. Soft quality metrics are reported against `targets.json` until calibrated.
