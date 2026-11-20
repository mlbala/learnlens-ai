# Privacy, copyright, and YouTube compliance

**Not legal advice.** Complete a legal review before public launch.

## Privacy / copyright disclaimer

- Users must **attest** they own or have permission to process each uploaded or pasted transcript before ingestion.
- LearnLens stores transcripts, derived notes, embeddings, and chat under the authenticated workspace. Do not treat public YouTube URLs as a license to copy audiovisual content.
- Operational logs must not contain raw transcript text, provider API keys, or model chain-of-thought.
- Users should be able to request deletion of authorized media/transcript, embeddings, and notes; cleanup spans Neon, Qdrant, and object/mock storage.
- AI provider transfers (when live providers are enabled) should be disclosed in product settings / privacy statement.

## Official YouTube compliance caveat

- LearnLens uses the **official YouTube Data API** for metadata (and official caption download only when the caller has edit permission — not implemented as a public-URL shortcut).
- A pasted public `watch` / playlist URL **does not** grant transcript access. Items remain `needs_transcript` until a permitted source is attached.
- The product does **not** implement unofficial scraping, signature decryption, or media downloaders.
- Embedded playback should use the official IFrame Player API; do not rehost YouTube media.
- Policy references: YouTube API Services Terms, Developer Policies, Captions API, IFrame API (see `docs/04_INGESTION_AND_COMPLIANCE.md` and `docs/11_SOURCES.md`).

## Fixture data notice

Synthetic fixtures under `fixtures/` (including `malicious_prompt.vtt` and golden transcripts) are **fixture data only**, not real YouTube captions or third-party copyrighted lesson text.
