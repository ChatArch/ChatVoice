# Configuration Reference

Enable only the capabilities you need. This reference follows the released `ChatVoiceConfig` schema. Keep credentials in server-side ChatEnv; the browser receives sanitized readiness only.

| Capability | Primary settings | Guide |
| --- | --- | --- |
| Transcription | ASR channel and local runtime or HTTP endpoint | [Web guide](web-guide.md#recording) |
| Notes, revision, Todo | Notes base, key and model | [Text models](text-models.md) |
| Automatic titles | Title base, key and model | [Text models](text-models.md) |
| System speech | TTS protocol, endpoint, key, model and voices | [TTS](tts-models.md) |
| Voice cloning | VoiceClone URL | [Voice cloning](voice-cloning.md) |
| Realtime | Legacy audio credentials and valid model entitlement | [Web guide](web-guide.md#realtime) |
| Copilot preview | Feature flag, notes text model and ASR | [Web guide](web-guide.md#copilot) |

## Use ChatEnv {#chatenv}

Install ChatVoice before provider discovery. Its canonical storage namespace is `ChatVoice` and its command alias is `chatvoice`.

```bash
chatenv status
chatenv init -t chatvoice -I
chatenv paste --stdin --profile speakr --yes
```

The last command reads `KEY=VALUE` text from standard input. Paste your values, finish input, then activate the named profile:

```bash
chatenv use speakr -t chatvoice -I
chatenv test -t chatvoice -I
```

The probe makes real text/TTS requests and can consume quota. Reload the service to apply startup configuration changes. ChatEnv does not automatically export variables to unrelated processes; runtime path overrides, CLI passwords and read tokens must also be supplied by the caller where required.

## Independent text models {#text}

| Field | Meaning |
| --- | --- |
| `CHATVOICE_MEETING_NOTES_API_BASE` | OpenAI-compatible base; `/chat/completions` is appended |
| `CHATVOICE_MEETING_NOTES_API_KEY` | Sensitive notes credential |
| `CHATVOICE_MEETING_NOTES_MODEL` | Notes model, also used for revisions and Todo |
| `CHATVOICE_MEETING_TITLE_API_BASE` | Independent title base |
| `CHATVOICE_MEETING_TITLE_API_KEY` | Sensitive title credential |
| `CHATVOICE_MEETING_TITLE_MODEL` | Title model identifier |

Setting an independent base or key requires the complete base/key/model triple for that purpose. You may explicitly configure equal values for both purposes, but missing values are never borrowed. Todo needs no additional model setting. The in-meeting Copilot fast answer path also reuses the notes model; missing notes configuration returns HTTP 503 and never borrows voice, title or browser-supplied arbitrary model settings.

```dotenv
CHATVOICE_MEETING_NOTES_API_BASE=https://model.example.com/v1
CHATVOICE_MEETING_NOTES_API_KEY=[REDACTED]
CHATVOICE_MEETING_NOTES_MODEL=notes-model
CHATVOICE_MEETING_TITLE_API_BASE=https://model.example.com/v1
CHATVOICE_MEETING_TITLE_API_KEY=[REDACTED]
CHATVOICE_MEETING_TITLE_MODEL=title-model
```

All example addresses, keys and model names are placeholders.

## Copilot preview {#copilot}

| Field | Default | Meaning |
| --- | --- | --- |
| `CHATVOICE_COPILOT_ENABLED` | `0` | Enables `/copilot`, app navigation and `/api/copilot/*` |
| `CHATVOICE_COPILOT_AUTO_PREPARE` | `0` | Allows speculative draft preparation; off by default, manual Submit remains available |
| `CHATVOICE_COPILOT_THINKING_MODE` | `provider-default` | Fast-answer thinking policy: `provider-default` adds no vendor field; `ark-disabled` sends Volcengine Ark `thinking.type=disabled` only for the Copilot request; other values fail closed |
| `CHATVOICE_ENV_PROFILE` | Empty | Load a named ChatEnv ChatVoice profile without changing the global active profile; missing names do not fall back to active |
| `CHATVOICE_PUBLIC_ORIGIN` | `http://127.0.0.1:18087` | Trusted fixed public origin for the user-management preview, for example `https://voice.example.invalid`; scheme/host/port only, no credentials/path/query/fragment, never derived from request Host |

Uploads accept TXT, Markdown, basic text PDFs and DOCX; URL fetch is not supported. Files are capped at 2 MiB, with declared and chunked body limits before multipart parsing. Answer/prepare JSON bodies are limited to 1 MiB before parsing. Authentication, CSRF and the preview flag are checked before the material form is parsed.

PDF parsing uses `pypdf>=6.19,<7.0` and validates direct-length streams, escaped names and decode limits before extraction. No-filter, Flate, ASCII85, ASCIIHex and RunLength streams are supported within those limits. Indirect lengths, nested streams, compressed object/xref streams, Form references, custom decode parameters and unsupported image/encryption/LZW filters fail closed. Re-export complex files as basic text PDFs or use TXT/Markdown. Scanned PDFs with no text do not receive OCR.

Copilot explicitly requests `max_tokens=384` and checks SSE line/event/aggregate bytes, event count, output length, a 60-second elapsed deadline and a 15-second socket-read timeout. The token parameter is not a spending guarantee. Disconnect, logout and session invalidation stop processing at cooperative read boundaries, close the response and never produce `done`. Partial output is not completion, and cancellation cannot reverse quota already spent. Owner and cookie/CSRF boundaries remain unchanged.

## ASR {#asr}

| Field | Default | Meaning |
| --- | --- | --- |
| `CHATVOICE_ASR_CHANNEL` | `api-server` when an endpoint exists; otherwise `stub-local` | `api-server`, `funasr-gpu`, `funasr-cpu` or `stub-local` |
| `CHATVOICE_ASR_API_URL` | Empty | Complete transcription endpoint |
| `CHATVOICE_ASR_API_KEY` | Empty | Optional sensitive Bearer credential |
| `CHATVOICE_ASR_PREWARM` | `1` | Prewarm the selected persistent local FunASR channel |
| `CHATVOICE_FUNASR_ALLOW_SUBPROCESS_WORKER` | `0` | Debug compatibility only; short-lived workers reload models per request |

Local FunASR also reads process variables `FUNASR_MODEL` (default `iic/SenseVoiceSmall`) and `FUNASR_GPU_DEVICE` (default `cuda:0`). They are not fields in the current typed ChatEnv schema. CPU uses the CPU; GPU requires compatible PyTorch/CUDA/FunASR dependencies. The stub channel is not real recognition.

## System TTS {#tts}

| Field | Meaning |
| --- | --- |
| `CHATVOICE_TTS_API_TYPE` | `openai`, `volcengine` or `qwen` |
| `CHATVOICE_TTS_API_BASE` | HTTP base; exact `ws/wss` endpoint for Qwen |
| `CHATVOICE_TTS_API_KEY` | Sensitive independent TTS credential |
| `CHATVOICE_TTS_MODEL` | Model identifier |
| `CHATVOICE_TTS_RESOURCE_ID` | Volcengine resource ID, separate from model |
| `CHATVOICE_TTS_VOICES` | JSON list of `id`/`label`; first voice is default |

Any nonempty independent field enables completeness checks. The resource ID is not required for `openai` or `qwen`; other required fields cannot be omitted. The Qwen path retains its `sk-sp` guard, which is not applied to other protocols. See [TTS examples and endpoint paths](tts-models.md).

## Voice cloning and runtime {#runtime}

| Field | Default | Meaning |
| --- | --- | --- |
| `CHATVOICE_VOICECLONE_URL` | Empty | VoiceClone service base |
| `CHATVOICE_VOICECLONE_TIMEOUT_SECONDS` | `180` | Request timeout in seconds |
| `CHATVOICE_HOME` | `$CHATARCH_HOME/chatvoice` or `~/.chatarch/chatvoice` | Runtime root; provide a process override consistently for CLI and service launcher |
| `CHATVOICE_SQLITE_PATH` | `data/meetings.sqlite3` under runtime root | Explicit database path supplied through the process environment |
| `CHATVOICE_REALTIME_MODELS` | Empty | Comma-separated allowlist, subject to backend support and entitlement |

`CHATARCH_HOME` is the shared ChatEnv home setting. See [runtime layout](runtime-layout.md) for path precedence and backup.

## Legacy deployment compatibility {#legacy}

These fields remain supported. Prefer independent text/TTS configuration for new deployments; Todo does not require legacy selectors.

| Field | Compatibility purpose |
| --- | --- |
| `CHATVOICE_OPENAI_API_BASE` | Legacy audio account HTTP base; defaults to the Token Plan compatible-mode endpoint |
| `CHATVOICE_OPENAI_API_KEY` | Sensitive legacy system-TTS/realtime credential; requires `sk-sp` |
| `CHATVOICE_OPENAI_API_MODEL` | Legacy text default when independent settings are absent; `qwen3.7-plus` |
| `CHATVOICE_MEETING_NOTES_PROVIDER` | Legacy notes selector; defaults to `token-plan-chat-completions` |
| `CHATVOICE_MEETING_NOTES_CRS_PROFILE` | Legacy external configuration reference |
| `CHATVOICE_MEETING_NOTES_CRS_API_BASE` | Legacy explicit base override |
| `CHATVOICE_MEETING_NOTES_CRS_API_KEY` | Sensitive legacy key override |

Independent text configuration takes precedence and fails if partial; it does not borrow these fields. Plan quota, API protocol and entitlement are separate concerns. Do not switch to usage-billed endpoints as an implicit exhaustion fallback.
