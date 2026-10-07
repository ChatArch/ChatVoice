# Web Guide

Speakr has three top-level modes: **meeting recording, voice studio and realtime conversation**. Transcript, summary, note refinement and Todo are views of the same meeting.

| Goal | Entry | Stored content |
| --- | --- | --- |
| Capture ideas or a meeting | Recording / transcript | Text, title and tags |
| Import existing audio or retain a recording | New-meeting mode button and import control | Recognition-only stores text; recording-and-transcription stores playable audio |
| Summarize and refine wording | Summary / note refinement | Summary and refinement conversation |
| Build an action plan | Convert to Todo below the summary | Markdown Todo and its conversation |
| Synthesize speech | Voice studio | Temporary preview/download, not generation history |
| Talk to an audio model | Realtime conversation | Conversation text |

## Choose storage

- **Account mode:** invited accounts synchronize records through the server with owner isolation.
- **Guest mode:** records live in this browser's IndexedDB. After refresh, choose guest mode again to open local history. Clearing browser data deletes those records.

Account and guest data do not automatically migrate between modes. Sending audio/text for model processing is not the same as retaining an audio archive. See [retention](recording-storage.md).

## Record and transcribe {#recording}

1. Create a meeting and check the ASR channel in settings.
2. A blank meeting defaults to **recognition-only**, discarding source audio without replay. Signed-in users may click **Enable recording + recognition** once before start; activation immediately greys and disables the button and retains this meeting's audio. Starting recognition-only without activation also disables it. Guests are recognition-only. Grant microphone access over HTTPS remotely.
3. Pause and let the current recognition window commit; resuming continues the same meeting.
4. Starting locks the mode permanently for this meeting. Finish and wait for the last recognition result; in recording-and-transcription, also wait for the audio-save confirmation before replay/download.

Edit or refresh the title, add tags, and open saved history. Copying a transcript does not export raw audio. Clearing, creating or deleting an active meeting interrupts recording resources; confirm that you intend to discard the active state.

The mode cannot switch after starting or finishing. Recognition-only cannot gain audio later, and a recording-and-transcription meeting cannot become recognition-only. A further recording requires a new meeting; pause/resume stays in the same capture. Clearing audio does not unlock the mode; deleting a meeting removes its associated files. Only the owner can replay/download audio. Archives are limited to 128 MiB.

## Import existing audio {#audio-import}

1. Sign in, then use **Import audio** to select a local file. Guests see a login explanation rather than an import that silently drops the audio.
2. WAV, MP3, WebM, Ogg, M4A/MP4 and FLAC are accepted up to 128 MiB per file; the configured ASR channel must support decoding the selected format.
3. The page shows upload/recognition status and a cancel control. Import always creates a recording-and-transcription meeting with retained, replayable original audio; continue with titles, summaries, note refinement and Todo.

An imported meeting is locked and cannot gain a second recording; an existing recognition-only meeting cannot be converted by import. Empty, invalid, oversized, failed or cancelled imports create no new meeting. Check history instead of resubmitting if cancellation was not confirmed; model computation may still need to finish normally. See [retention and backup](recording-storage.md).

## Summarize and refine {#summary}

The summary view supports update and copy. Note refinement provides an editable canvas and a conversation panel for audience changes, emphasis, action items and omissions. Manually or conversationally customized notes are not automatically overwritten by resumed recording. Explicit regeneration still needs review.

Failed or incomplete revision streams preserve the prior canvas. Undo restores the text before the latest model revision. Notes and titles can use different configured text models; missing text settings are not filled from voice credentials.

## Markdown Todo {#todo}

Click **Convert to Todo** below the summary to open a separate Todo page. It may also start empty: type Markdown yourself and refine it through conversation.

Todo text and its conversation do not overwrite the summary. Copy or download `.md`; change `- [ ]` to `- [x]` to mark completion. The current surface is a Markdown text editor, not a mind map. See the [Todo guide](markdown-todo.md).

## Voice studio {#studio}

System voices and the cloned-voice option share one text input. System voices come from server configuration and support the displayed MP3/WAV options. Cloning needs an uploaded or recorded reference and explicit voice consent.

System TTS and voice cloning use different backends. One failing does not establish failure of the other; inspect the displayed configuration and connection state. See [voice cloning](voice-cloning.md).

## Realtime conversation {#realtime}

Choose an allowed model and voice, then start the conversation. Saved text can be reviewed and exported. The current realtime proxy targets Qwen audio interfaces, not arbitrary text models.

A listed model, a successful socket connection or a session-created event does not prove generation entitlement. Resolve quota/subscription errors explicitly; there is no implicit usage-billed fallback.
