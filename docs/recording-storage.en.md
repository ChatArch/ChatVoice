# Data Retention Boundary

Saving a meeting means saving text and metadata, not an archive of its raw recording.

| Data | Account mode | Guest mode |
| --- | --- | --- |
| Title, tags, transcript | Owner-isolated server SQLite | Current-browser IndexedDB |
| Summary and refinement chat | Stored with the meeting | Stored with the local meeting |
| Markdown Todo and refinement chat | Stored with the meeting | Stored with the local meeting |
| Realtime conversation text | Stored with the conversation | Browser-local record |
| Raw meeting recording | No recording archive | No recording-chunk archive |
| Provider credentials | Server-side configuration only | Never sent to the browser |

## Processing is not archiving

Microphone audio passes through the browser, ChatVoice and the selected ASR backend. The server may temporarily use `temp/asr` for decoding/recognition and cleans files during normal processing. External ASR/text providers have their own data policies.

Not retaining meeting recordings does not mean audio never crosses the network or disk, nor that guest recognition runs offline.

## Voice studio output

System TTS and cloning generate task audio for preview/download; this is distinct from downloading a meeting recording. Cloning requires an authorized reference and does not create a reusable voice library or generation history. Session reference audio is not a permanent asset.

## Deletion and backups

- Clearing browser data deletes guest records. Signing in does not automatically upload them.
- Deleting server records requires ownership and CSRF validation.
- Exported Markdown, database backups and third-party copies have their own lifecycle.
- Code rollback must not restore a stale database over newer records.

[Runtime and backup](runtime-layout.md) · [Access and API](api-access.md)
