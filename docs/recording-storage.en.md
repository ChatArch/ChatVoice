# Data Retention Boundary

Every blank meeting has exactly two routes: **recognition-only** discards all source audio and has no replay; signed-in users may choose **recording + recognition** before start to retain and replay this meeting.

| Data | Account mode | Guest mode |
| --- | --- | --- |
| Title, tags and transcript | Owner-isolated server SQLite | Current-browser IndexedDB |
| Summary, note refinement, Markdown Todo and conversations | Stored with the meeting | Stored with the local meeting |
| Original meeting recording | Recognition-only discards it; recording + recognition retains it privately | Recognition-only; no recording archive |
| Imported original file | Always privately retained and replayable | Import is unavailable with a visible login explanation |
| Realtime conversation text | Stored with the conversation | Browser-local record |
| Provider credentials | Server-side only | Never sent to the browser |

## Choose a recording mode

| Mode | Behavior | Available to |
| --- | --- | --- |
| Recognition-only | Discard all source audio after processing and expose no replay | Default for accounts and guests |
| Recording + recognition | Capture from recording start, associate it with this meeting after normal completion, and allow replay | Logged-in accounts |

The first recognition/recording start persistently locks the route before transcript text arrives. Pause/resume and normal tail finalization remain part of that capture. After finish, create a new meeting for more audio. Clear, reopen and reload do not unlock, and started meetings reject another recording or import. Recording archives remain limited to 128 MiB.

The backend stores lock, start/final state and owned capture identity, rejecting later changes in either direction. Legacy records and mixed retained assets migrate conservatively as finished and are never deleted by classification.

## Import existing audio

Use the audio-import control in the meeting recorder. WAV, MP3, WebM, Ogg, M4A/MP4 and FLAC containers are accepted up to 128 MiB per file; actual decoding depends on the selected ASR channel. Successful import opens a normal meeting for titles, summaries and note refinement, not a separate audio library.

Import always creates a locked, finished recording + recognition meeting and retains the original for replay; retention is not optional. Import requires login, while guests receive a visible explanation rather than a silent text-only downgrade. Recognition failures, empty results, cancellation and storage failures create no half-finished meeting. Cancellation prevents result commit but cannot promise immediate upstream interruption.

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
