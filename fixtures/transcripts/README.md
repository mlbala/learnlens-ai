# Transcript fixtures

Synthetic fixture data for offline tests. Not real YouTube captions.
Do not treat these strings as authorized third-party content.

| File | Purpose |
| --- | --- |
| `sample.srt` / `sample.vtt` / `sample.txt` | Small happy-path parses |
| `long_fixture.srt` | Multi-cue fixture for chunking/chapters (includes injection-like lines as **data**) |
| `malicious_prompt.vtt` | Adversarial corpus (ignore instructions, forged roles, URLs, encoded payloads) — fixture data only |
| `malformed.srt` | Negative parse cases |
