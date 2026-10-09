# HTTP API

Web sessions, stored records and model processing have distinct boundaries. All paths below are relative to your service origin.

| Group | Authorization | Purpose |
| --- | --- | --- |
| Sessions | Account login and cookies; CSRF for writes | Invited-account sessions |
| Meeting/conversation storage | Cookie, owner checks and `X-CSRF-Token` for writes | Your saved records |
| Data export | Bearer token with matching scope | Programmatic read-only export |
| Text/ASR/TTS processing | Currently callable by guests; model keys remain server-side | Process content, not automatically save records |
| Voice-cloning jobs | Account, job ownership and CSRF for create/delete | Authorized one-shot synthesis |
| Copilot | Account cookies and owner checks; CSRF for writes | Preview materials and fast answers |

!!! warning "Protect public processing endpoints"
    Model-processing routes are not Bearer data-export routes. Operators must control abuse and upstream quota. Hiding credentials from the browser does not make unrestricted model access safe.

## Shared login component {#login-ui}

ChatVoice directly uses `ChatLogin>=0.1.2,<0.2.0` and its built-in `ChatVoiceAuth` backend, preserving existing account/session schema, password material and cookies. The host retains only connection callbacks, HTTP mapping and business policy.

`/login` renders shared LoginUI forms, CSS and scripts with host branding. Supply another theme or trusted template from the Python entrypoint without editing site-packages:

```python
from chatlogin.ui import LoginUI
from chatvoice.web import create_app

app = create_app(login_ui=LoginUI(
    title="My voice workspace", palette="forest", layout="split",
    appearance="system", guest_url="/?mode=guest",
))
```

Drafts are saved and the IndexedDB transaction must complete before leaving for login. Abort/save failure or an active recording/realtime conversation prevents navigation. Guest records are not uploaded automatically; passwords, sessions and CSRF are not written to browser persistent storage.

## Health, sessions and records {#records}

| Method and path | Purpose |
| --- | --- |
| `GET /api/heartbeat` | Version, database state and ASR prewarm/heartbeat |
| `GET /api/status` | Sanitized configuration and model/backend status |
| `GET /login` | Customizable shared ChatLogin page |
| `POST /api/auth/login` | `account` or `username`, `password`, optional safe local `next`; returns user/CSRF/redirect data and sets a session cookie |
| `GET /api/auth/session` | Current session state |
| `POST /api/auth/logout` | End a session; CSRF required |
| `POST /api/auth/register` | Disabled self-registration; HTTP 403 |
| `GET /api/meetings` | Current owner's meeting metadata |
| `GET/PUT/DELETE /api/meetings/{id}` | Meeting detail, save or delete |
| `GET /api/conversations` | Current owner's conversation metadata |
| `GET/PUT/DELETE /api/conversations/{id}` | Conversation detail, save or delete |

Meeting writes contain title, timestamps, duration, tags, transcript segments, summary/refinement conversation and `todo_markdown` / `todo_chat_messages`. Detail responses include content; lists stay lightweight. Older clients omitting Todo fields preserve existing values; explicit empty text/lists clear them.

## Meeting-audio retention and import {#meeting-audio}

These endpoints require account cookies and ownership, with CSRF for writes. Read-only data tokens do not automatically grant audio-file access.

| Method and path | Input and result |
| --- | --- |
| `POST /api/meetings/{id}/capture/start` | JSON `meeting_mode`, `capture_token`; atomically lock a blank meeting and own its capture |
| `POST /api/meetings/{id}/capture/finish` | JSON `capture_token`; mark the matching started capture finished, idempotently |
| `POST /api/meetings/{id}/audio` | Multipart `file`, `upload_token`, `capture_token`, `generation`; normal recording-route tail, up to 128 MiB |
| `GET /api/meetings/{id}/audio/{audio_id}` | Private playback with controlled audio MIME and no caching |
| `GET /api/meetings/{id}/audio/{audio_id}/download` | Attachment download of the same private file |
| `DELETE /api/meetings/{id}/audio` | Delete all associated audio and increment recording generation |
| `POST /api/meetings/{id}/import` | Multipart `file`, `import_token`, optional `channel`, `correct`; always retains source, up to 128 MiB |
| `DELETE /api/meeting-imports/{import_token}` | Cancel an owned import, also removing a just-committed meeting in a completion race |

Meeting writes return `meeting_mode`, `mode_locked` and `capture_state`; legacy `audio_retention` still maps to the two modes, and omitted mode fields preserve the current choice. Explicit reverse mutation after lock returns 409. Details also include `audio_assets` and read-only `audio_generation`. Recognition-only has no audio asset/replay. Recording uploads validate both capture ownership and generation; stale uploads after clear return 409.

Import requires an account, never overwrites a meeting, and returns a locked, finished recording + recognition meeting with replayable source. Even legacy `retain_audio=false` cannot downgrade it. Repeating a completed token returns the existing result; cancelled/failed tokens cannot silently recognize again. Empty files return 400, size limits 413, invalid container/MIME 415, conflicts/cancellation 409, invalid model output 502, storage failure 503, and ASR timeout 504. Failures create no half-finished meeting.

## Text processing {#text}

| Method and path | Input | Output |
| --- | --- | --- |
| `POST /api/meeting-title` | `transcript`, optional `model` | `title`, `model` |
| `POST /api/meeting-notes/polish` | `transcript`, optional `instruction`/`model` | `content`, `model` |
| `POST /api/meeting-notes/revise/stream` | `transcript`, `current_summary`, `instruction`, optional `messages`/`model` | SSE `meta`, `delta`, `done` or `error` |

Revision deltas use canvas/reply separator markers. Require explicit `done`; socket EOF is not completion. Keep the prior document when the stream fails.

## Copilot preview {#copilot}

When `CHATVOICE_COPILOT_ENABLED=1` is set:

| Method and path | Purpose |
| --- | --- |
| `GET /copilot` | Chinese-first in-meeting assistant page |
| `GET /api/copilot/status` | Enabled state, material limits and preparation policy |
| `GET /api/copilot/materials` | Current owner's materials |
| `POST /api/copilot/materials` | Multipart `file`; TXT/MD/PDF/DOCX, CSRF required |
| `DELETE /api/copilot/materials/{id}` | Delete your material, CSRF required |
| `POST /api/copilot/answer/stream` | SSE fast answer, CSRF required |
| `POST /api/copilot/prepare` | Optional speculative preparation; returns 409 when disabled |

Material files are capped at 2 MiB, with declared and actual body limits before multipart parsing. Answer/prepare JSON bodies are capped at 1 MiB before parsing. PDFs accept basic text and bounded direct-length streams; escaped names participate in validation. Complex object/xref/Form layouts, nested streams, custom decode parameters, indirect lengths and unsupported filters are rejected before extraction. Re-export complex files as basic text PDFs or use TXT/Markdown; scanned files do not receive OCR.

Answer stream events are `meta`, `delta`, `done` or `error`. `meta.evidence` contains retrieved snippets, not verified external citations; clients must wait for `done.completion_marker == "copilot.answer.done"`. Copilot explicitly requests `max_tokens=384`, and separately checks SSE line/event/aggregate bytes, event count, output length, a 60-second elapsed deadline and a 15-second socket-read timeout. Disconnect, logout, invalid sessions, limit errors and truncation produce no `done`; partial output is not completion. Requests bind `request_id`, `transcript_revision` and `material_revision`; clients discard late or stale results.

## Markdown Todo {#todo}

Generation processes the supplied summary and does not create a meeting record:

```http
POST /api/meeting-notes/todo
Content-Type: application/json
```

```json
{"summary":"Collect the key findings, draft the article, then check citations."}
```

The response contains the full Markdown `content` and `model`. A source without actionable work returns an explicit no-actions result instead of fabricated tasks.

Conversation refinement:

```http
POST /api/meeting-notes/todo/revise
Content-Type: application/json
```

```json
{
  "summary": "Organize the research and write an article.",
  "current_todo": "# Todo\n- [x] Confirm topic\n- [ ] Write a draft",
  "instruction": "Split drafting into two steps and preserve completion states.",
  "messages": []
}
```

The response contains complete `content`, short `reply`, and `model`. Summary/current text are each limited to 20000 characters; the instruction to 2000; history to 12 messages, each with `role: user|assistant` and `text`. Save the resulting Markdown through the normal meeting-write endpoint.

## Audio processing {#audio}

| Method and path | Purpose |
| --- | --- |
| `GET /api/asr/channels` | Available recognition channels |
| `POST /api/asr` | Multipart `file`, optional `channel`/`correct`; returns `raw_text`, `corrected_text`, `channel`, `meta` |
| `WS /ws/asr/stream` | Bounded PCM16 protocol used by the browser, not a generic cloud-ASR protocol |
| `POST /api/tts` | JSON `text`, optional `voice`, `format` (`mp3` / `wav`); returns audio |
| `GET /api/realtime/models` | Model selection list, not entitlement proof |
| `WS /ws/realtime?model={id}` | Current Qwen realtime proxy |

Independent TTS returns metadata including `X-TTS-Provider`, `X-TTS-Model` and `X-TTS-Voice`. Validate the actual audio, not HTTP 200 alone.

VoiceClone uses `GET /api/voice-clone/status`, `POST /api/voice-clone/jobs`, `GET/DELETE /api/voice-clone/jobs/{id}` and `GET /api/voice-clone/jobs/{id}/audio`. See [voice cloning](voice-cloning.md) for consent and temporary-job boundaries.

Job creation accepts multipart `reference_audio`, `text`, and optional `lang` / `duration_factor`. The web flow handles consent confirmation; this API has no `consent` field, and callers remain responsible for reference-voice authorization.

## Tokens and exports {#tokens}

Create/revoke tokens in web settings, or use the CLI:

```bash
chatvoice tokens create --url https://speakr.example.com --account member@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name export --expires-days 30 --scope read:meetings --json
chatvoice data meetings --url https://speakr.example.com --token-env CHATVOICE_DATA_READ --json
chatvoice data meeting MEETING_ID --url https://speakr.example.com --token-env CHATVOICE_DATA_READ --json
```

Supply the one-time token securely through `CHATVOICE_DATA_READ`, never public logs. `read:meetings` grants `/api/data/meetings[/{id}]`; `read:conversations` grants `/api/data/conversations[/{id}]`. Tokens cannot cross owners or expand their scope.

| Status | Typical meaning |
| --- | --- |
| 401 | Missing/expired session or token |
| 403 | CSRF, scope, permission or disabled operation |
| 404 | Missing record or another owner's record |
| 422 | Invalid input shape or length |
| 503 | Missing/incomplete required configuration |
| 502 | Upstream failure or invalid/incomplete model output |

[Python client](interface-tree.md) · [Troubleshooting](troubleshooting.md)
