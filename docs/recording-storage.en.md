# Data Retention Boundary

Original meeting audio is **discarded by default**. Account users may explicitly opt in before recording or importing. Processing audio and retaining it are different operations.

| Data | Account mode | Guest mode |
| --- | --- | --- |
| Title, tags and transcript | Owner-isolated server SQLite | Current-browser IndexedDB |
| Summary, note refinement, Markdown Todo and conversations | Stored with the meeting | Stored with the local meeting |
| Original meeting recording | Discarded by default; private retention only after opt-in | No server or browser recording archive |
| Imported original file | Deleted after processing by default; optional private retention | Only the recognized text record is saved |
| Realtime conversation text | Stored with the conversation | Browser-local record |
| Provider credentials | Server-side only | Never sent to the browser |

## Choose a recording mode

| Mode | Behavior | Available to |
| --- | --- | --- |
| Transcribe without saving audio | No meeting-audio archive buffer or persistent recording file | Default for accounts and guests |
| Save original recording | Capture browser-encoded audio from recording start and associate it with the meeting after normal completion | Logged-in accounts |

Pause and resume belong to the same recording. After finishing, wait for the saved-audio confirmation. Starting another recording after completion creates another audio asset, rather than replacing earlier files. A new pass cannot start while its predecessor is still saving. Recording archives are limited to 128 MiB; an exceeded limit or browser recording failure has an explicit error, not a successful-save claim.

Changing mode affects later recordings only. It neither deletes existing files nor recovers discarded audio. Clearing, creating or deleting an active meeting interrupts and discards incomplete capture; finish and confirm saving before switching meetings if you need the current recording.

## Import existing audio

Use the audio-import control in the meeting recorder. WAV, MP3, WebM, Ogg, M4A/MP4 and FLAC containers are accepted up to 128 MiB per file; actual decoding depends on the selected ASR channel. Successful import opens a normal meeting for titles, summaries and note refinement, not a separate audio library.

In account mode, the recording-mode choice also controls original-file retention. With retention off, staged files are removed after normal processing. Guests only create browser-local text meetings. Recognition failures, empty results, cancellation and storage failures do not create half-finished meetings. Cancellation prevents result commit, but cannot promise immediate interruption of upstream or already-running model computation. Check history instead of submitting again if cancellation was not confirmed.

Files over 12 MiB require FFmpeg on the main-service host. Decoding produces sequential 30-second, 16-kHz mono WAV windows through the selected ASR channel and reuses the existing persistent GPU model. Server recognition has a 15-minute budget with cancellation checks between windows. The browser has a 30-minute total upload-and-recognition budget; a long upload consumes that total. Allow 128 MiB plus multipart overhead at the reverse proxy and an ASR request wait of at least 1020 seconds. Smaller files retain the original ASR path.

## Private files and deletion

- Retained files live in runtime `data/meeting-audio/`, using server-generated names, `0700` directories and `0600` files.
- Playback and download require a valid account session and meeting ownership. They are not anonymous links; read-only data tokens do not automatically grant audio-file access.
- Clearing a meeting deletes associated audio and invalidates old uploads; deleting a meeting also cleans its audio. Cleanup failures are reported rather than counted as successful deletion.
- Downloaded, exported, backed-up or third-party copies have independent lifecycles. Confirm authorization before retaining or using recordings.

## Processing is not archiving

Microphone and imported audio pass through the browser, ChatVoice and the selected ASR provider. Temporary files under `temp/asr` or `temp/audio-uploads` may be used for decoding, recognition or validation and are removed during normal cleanup. External services have their own policies. Discarding recordings does not mean audio never crosses the network or disk, nor that guest transcription works offline.

Voice-studio TTS/cloning output remains temporary task preview/download audio. Cloning requires an authorized reference and creates neither a permanent voice library nor generation history. The meeting retention mode does not retain raw realtime-conversation audio.

## Backups

`chatvoice data dump` backs up SQLite only, not recording bytes. When retaining audio, stop the service normally and back up or restore the consistent database snapshot together with `data/meeting-audio/`. Restoring only the database cannot recover missing recordings. Code rollback must not overwrite newer records with a stale database.

[Runtime and backup](runtime-layout.md) · [Access and API](api-access.md) · [Web guide](web-guide.md)
