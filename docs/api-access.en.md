# HTTP API

Web sessions, stored records and model processing have distinct boundaries. All paths below are relative to your service origin.

| Group | Authorization | Purpose |
| --- | --- | --- |
| Sessions | Account login and cookies; CSRF for writes | Invited-account sessions |
| Meeting/conversation storage | Cookie, owner checks and `X-CSRF-Token` for writes | Your saved records |
| Data export | Bearer token with matching scope | Programmatic read-only export |
| Text/ASR/TTS processing | Currently callable by guests; model keys remain server-side | Process content, not automatically save records |
| Voice-cloning jobs | Account, job ownership and CSRF for create/delete | Authorized one-shot synthesis |

!!! warning "Protect public processing endpoints"
    Model-processing routes are not Bearer data-export routes. Operators must control abuse and upstream quota. Hiding credentials from the browser does not make unrestricted model access safe.

## Health, sessions and records {#records}

| Method and path | Purpose |
| --- | --- |
| `GET /api/heartbeat` | Version, database state and ASR prewarm/heartbeat |
| `GET /api/status` | Sanitized configuration and model/backend status |
| `POST /api/auth/login` | `account` and `password`; returns user/CSRF data and sets a session cookie |
| `GET /api/auth/session` | Current session state |
| `POST /api/auth/logout` | End a session; CSRF required |
| `POST /api/auth/register` | Disabled self-registration; HTTP 403 |
| `GET /api/meetings` | Current owner's meeting metadata |
| `GET/PUT/DELETE /api/meetings/{id}` | Meeting detail, save or delete |
| `GET /api/conversations` | Current owner's conversation metadata |
| `GET/PUT/DELETE /api/conversations/{id}` | Conversation detail, save or delete |

Meeting writes contain title, timestamps, duration, tags, transcript segments, summary/refinement conversation and `todo_markdown` / `todo_chat_messages`. Detail responses include content; lists stay lightweight. Older clients omitting Todo fields preserve existing values; explicit empty text/lists clear them.

## Text processing {#text}

| Method and path | Input | Output |
| --- | --- | --- |
| `POST /api/meeting-title` | `transcript`, optional `model` | `title`, `model` |
| `POST /api/meeting-notes/polish` | `transcript`, optional `instruction`/`model` | `content`, `model` |
| `POST /api/meeting-notes/revise/stream` | `transcript`, `current_summary`, `instruction`, optional `messages`/`model` | SSE `meta`, `delta`, `done` or `error` |

Revision deltas use canvas/reply separator markers. Require explicit `done`; socket EOF is not completion. Keep the prior document when the stream fails.

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
