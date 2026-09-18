# Web Guide

Speakr has three top-level modes: **meeting recording, voice studio and realtime conversation**; preview deployments can also enable **Copilot**. Transcript, summary, note refinement and Todo are views of the same meeting.

| Goal | Entry | Stored content |
| --- | --- | --- |
| Capture ideas or a meeting | Recording / transcript | Text, title and tags |
| Summarize and refine wording | Summary / note refinement | Summary and refinement conversation |
| Build an action plan | Convert to Todo below the summary | Markdown Todo and its conversation |
| Synthesize speech | Voice studio | Temporary preview/download, not generation history |
| Talk to an audio model | Realtime conversation | Conversation text |
| Answer during a meeting | Copilot | Extracted material text and answer state |

## Choose storage

- **Account mode:** invited accounts synchronize records through the server with owner isolation.
- **Guest mode:** records live in this browser's IndexedDB. After refresh, choose guest mode again to open local history. Clearing browser data deletes those records.

Account and guest data do not automatically migrate between modes. Sending audio/text for model processing is not the same as retaining an audio archive. See [retention](recording-storage.md).

## Record and transcribe {#recording}

1. Create a meeting and check the ASR channel in settings.
2. Start recording and grant microphone access. Remote access should use HTTPS.
3. Pause and let the current recognition window commit; resuming continues the same meeting.
4. Finish and wait for the last recognition result before reviewing the summary.

Edit or refresh the title, add tags, and open saved history. Copying a transcript does not export raw audio. Clearing, creating or deleting an active meeting interrupts recording resources; confirm that you intend to discard the active state.

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

## Copilot preview {#copilot}

When enabled, **Copilot** appears in navigation and `/copilot` is available. The left column holds materials and pre-meeting instructions, the middle column reuses `/ws/asr/stream` for live transcript/current question state, and the right column shows fast answers, preparation state and evidence.

Materials are local TXT, Markdown, PDF or DOCX files only; URL fetch is not supported. Scanned PDFs report OCR-not-supported. If the user selects "mic + browser tab" and the browser returns no tab audio track, the page reports an error and stops instead of silently recording only the user's mic. Stop, page teardown, reset and logout close mic tracks, audio graphs, WebSockets, timers and pending UI work.

Answers use the existing meeting-notes text model settings. Evidence is retrieved context, not verified external citation; a human should still judge live answers. Background preparation is off by default. When enabled, drafts bind transcript revision, material revision, instructions and request ID; stale drafts do not overwrite newer questions.
