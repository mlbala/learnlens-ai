# 04 — YouTube Metadata, Authorized Content Ingestion, Compliance

## 1. Verified constraints

- YouTube Data API `playlistItems.list` enumerates public playlist items with paging and a maximum page size of 50. It exposes metadata, **not arbitrary transcripts**.
- YouTube `captions.download` explicitly requires that the authorized user have permission to edit the video. A public URL does not confer this access.
- YouTube API policies and other applicable terms restrict use of audiovisual content. Do not implement unofficial scraping, signature decryption or downloader fallbacks as part of this blueprint.
- Original embedded YouTube playback should use the official IFrame Player API; do not copy or rehost YouTube media.

Authoritative links:
- https://developers.google.com/youtube/data/reference/rest/v3/playlistItems/list
- https://developers.google.com/youtube/data/reference/rest/v3/captions/download
- https://developers.google.com/youtube/terms/developer-policies
- https://developers.google.com/youtube/iframe_api_reference

## 2. Content acquisition matrix

| Input | Supported action | Timed citations? |
| --- | --- | --- |
| Video URL, no transcript | Fetch metadata, show embed and `needs_transcript` | No |
| Playlist URL | Fetch order, metadata, availability and aggregate coverage | Only on items with eligible timed source |
| User uploaded SRT/VTT with permission | Parse and attach to matching video, process | Yes: original/verified timecodes |
| User pasted plain transcript with permission | Process text, mark `timecode_quality=none` | No |
| User uploaded TXT with permission | Process text without inventing timing | No |
| Creator-authorized caption download | Official OAuth permissions and API method; optional post-MVP | Yes, if timing present |
| User-uploaded video/audio with rights | Opt-in separate media pipeline, strict size/type handling; optional | Yes only if derived timing alignment verified |
| Third-party caption scraper | **Not supported** | N/A |

## 3. Video/playlist URL normalization

Accepted `https://www.youtube.com/watch?v=...`, `https://youtu.be/...`, `https://www.youtube.com/shorts/...`, `https://www.youtube.com/playlist?list=...` and equivalent exact allowed subdomains. Do not allow `youtube.com.evil.example` or `user:pass@youtube.com`; reject ports/non-HTTPS/invalid hostnames, redirects to unknown hosts, private IPs, localhost, Unicode tricks and percent-encoded host confusion. Parse IDs with strict validation. Fetch only constructed official Google endpoints; never make arbitrary outbound requests to the user-supplied URL. Canonicalize and store original only for audit (careful redaction of query params unrelated to video identity).

For `watch?v=...&list=...`: ask via the UI or choose predictable API behavior: import a **single video** from `v` with a visible “Import playlist instead” affordance; never silently import hundreds of items.

## 4. API quota and pagination

`playlistItems.list` maximum 50 per request; use page token until exhausted, with a configurable total cap. Observe quota consumption; cache metadata refresh subject to YouTube retention policy. Private/unavailable/deleted videos may be represented differently; persist positions and states without leaking metadata not supplied by official API. Use backoff for 429/5xx and stop on policy/authorization errors. Normalize thumbnails to documented source references and respect API retention/deletion rules.

## 5. Upload validation, provenance and storage

- Explicit checkbox: “I own this transcript or have the necessary permission to process it.” Store actor, timestamp, source type, file hash.
- Only `.srt`, `.vtt`, `.txt` in MVP; detect MIME/content independent of extension, reject executables, archives and binary payloads. Default max upload 10 MB and max 200k characters per item, configurable.
- Normalize UTF-8 (BOM allowed), detect malformed/overlapping cues, invalid negative or decreasing timecodes. Reject absurd durations or segments; report which line/cue failed without returning transcript to logs.
- Store sensitive upload content outside public web root, private directory or object bucket; randomized storage keys; no path traversal, symlink escaping, zip bombs or public direct URLs.
- Remove scripts and HTML as presentation elements; **preserve quoted transcript text** as source data; render via safe escaped components, not dangerouslySetInnerHTML.
- Content hashes support idempotency and repeated job de-duplication.
- Do not expose uploaded data to AI providers without disclosure/consent setting in UI and privacy statement.

## 6. Timestamps and evidence mapping

For captioned segments, store `start_ms`, `end_ms` from original timecodes and stable segment IDs. Aggregated chunk time range is min/max of constituent timed segments. A source citation requires the segment ID to be in the verified evidence set. For plain text input, `start_ms=null`, no fake approximate offset. If an AI says “at 5:32” without timed evidence, strip that claim and block timestamp link generation.

`youtube_url` for time links is server-constructed `https://www.youtube.com/watch?v=<validated-id>&t=<seconds>s`, with start seconds derived from stored milliseconds. Provider output cannot provide arbitrary URLs.

## 7. Playlist lifecycle and incomplete sources

For a playlist with 15 items: 10 `ready`, 2 `needs_transcript`, 1 `unavailable`, 2 `failed`. UI shows **10/15 supported video lessons**, with 2 awaiting content, 1 unavailable and 2 errors. Playlist synthesis uses only 10 ready transcripts. It lists excluded IDs, does not write paragraphs about the five unsupported videos, and marks result `partial`.

A playlist summary should be invalidated when a member transcript changes, a member becomes available, or the playlist order changes. Aggregate reprocessing can reuse cached per-video summaries.

## 8. Privacy, retention and user controls

Delete authorized media/transcript, embeddings and notes on request; run cleanup on DB, Qdrant and object storage with durable job tracking. Default private; expose clear settings for transcript upload, provider transfers, data deletion and retention. Do not store raw transcripts in operational event logs, trace payloads, provider error blobs or analytics. Complete legal review before public release; the design is not legal advice.

## 9. Acceptance tests

- Public URL returns metadata without claiming transcript access.
- `needs_transcript` item cannot be marked summarized.
- Playlist 3/5 ready is correctly flagged partial; unsupported items excluded.
- Unauthorized file/content source cannot be imported under another workspace.
- Malicious URL and malformed SRT/VTT rejected with safe error codes.
- Plain text generates no timestamped citation.
- YouTube data usage stays within permissions and has actionable documented limitations.
