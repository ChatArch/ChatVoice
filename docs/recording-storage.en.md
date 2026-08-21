# Recording Storage Boundary

The current ChatVoice / Speakr meeting recorder saves text and summaries only. It does not save original recording files.

## What the current version saves

Signed-in account mode stores on the server:

- meeting title, timestamps, duration, and metadata;
- realtime transcript segments;
- AI summaries, action items, and note-editing content;
- API token hash, prefix, scopes, expiration, and delete/revoke state.

Guest mode stores in the current browser:

- guest meeting text, summaries, and metadata;
- guest realtime conversation text.

## What the current version does not save

The meeting recorder does not save:

- original recording files;
- replayable full meeting audio;
- browser-local audio chunks;
- raw audio in backend object storage or SQLite;
- recording files readable through API tokens.

In short: the meeting recorder has no “save recording” or “download recording” feature. Audio is used only for realtime transcription; the durable result is text and summaries.

## How audio flows during transcription

During recording, the browser streams microphone audio to the backend ASR channel:

```text
microphone audio -> ChatVoice ASR WebSocket -> ASR service -> transcript text -> meeting record / summary
```

This flow exists to produce text. The current version does not persist that audio stream as a replayable file and does not keep audio chunks in browser IndexedDB.

## Why there is no “save locally” button

A “save locally” control makes users wonder whether the system already saved audio, or whether the server also has a copy. The current product boundary is:

> The server stores text and summaries only; original recordings are not saved.

For that reason, the current version does not expose local recording archive/download controls. This keeps the recorder privacy model simple and avoids extra user burden.

## Future pure-recording support

If ChatVoice later adds “pure recording” or a recording file library, it should be a separate feature instead of part of the default meeting transcription flow. That design should explicitly cover:

- whether files are stored on the server;
- whether files are browser-local only;
- file format, size, and retention period;
- deletion policy;
- whether API tokens may read recordings;
- how the UI separates “meeting text records” from “recording files”.

Until that feature is designed and shipped, the meeting recorder does not save original audio.
