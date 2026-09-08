# Independent TTS Configuration

`0.1.15.post2` is a local, unpublished source hotfix. Only system speech synthesis changes; ASR, realtime conversation, notes/title, VoiceClone, accounts and storage remain unchanged. Configuration uses the same ChatEnv `ChatVoice` provider, with no new browser settings page.

## Configuration

| Field | Rule |
| --- | --- |
| `CHATVOICE_TTS_API_TYPE` | `volcengine`, `openai` or `qwen`; dispatch uses protocol, not model name |
| `CHATVOICE_TTS_API_BASE` | HTTP(S) root API base for Volcengine/OpenAI; exact ws/wss WebSocket endpoint for Qwen, with no path appended |
| `CHATVOICE_TTS_API_KEY` | Independent sensitive credential, never borrowed from notes/title/realtime/global keys |
| `CHATVOICE_TTS_MODEL` | Configured model identifier; sent as model for OpenAI, while Volcengine routes by its separate resource |
| `CHATVOICE_TTS_RESOURCE_ID` | Required for Volcengine, distinct from display/model identifier; optional for OpenAI/Qwen |
| `CHATVOICE_TTS_VOICES` | Nonempty JSON array `[{"id":"configured-voice","label":"Display name"}]`; first entry is default |

At most 64 voices; ids and labels are each unique and at most 80 characters. IDs use printable ASCII; labels exclude controls and angle brackets. `clone` is reserved for the existing clone card. Model identifiers use at most 256 printable ASCII characters. Never put credentials in identifiers or labels.

Any nonempty independent field opts in. Incomplete configuration, unknown protocols, unsafe URLs and malformed catalogs return TTS 503 without fallback. Only all six fields empty preserve the legacy Qwen `sk-sp` gate/call. Bases reject userinfo, queries, fragments and controls. Redirects are never followed. Use HTTPS in production and HTTP only on trusted networks.

Public base examples: Volcengine `https://openspeech.bytedance.com/api/v3/plan`; OpenAI-compatible `https://api.openai.com/v1`. Operators must configure the endpoint's actual model, resource and voices; there are no implicit provider-specific defaults.

### Explicit Qwen WebSocket protocol

Set `CHATVOICE_TTS_API_TYPE=qwen` and configure the same independent BASE/KEY/MODEL/VOICES fields. BASE is the **exact** ws/wss URL, including its path and any trailing slash; for example, the public Token Plan endpoint is `wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference`. No operation path is appended. The independent KEY must pass the existing `sk-sp` Token Plan guard; ordinary usage-billed keys are rejected. RESOURCE_ID is optional and unused by this protocol. Model and voice IDs come exclusively from this configuration, not from `CHATVOICE_OPENAI_*` or SDK/environment defaults.

Each call uses its own synchronous `websocket-client` connection and explicit Authorization header. It sends `run-task`, waits for matching `task-started`, sends `continue-task` with text and `finish-task`, then requires matching `task-finished` and nonempty structurally valid MP3/WAV audio. The generated task ID correlates events; upstream error bodies are never exposed. MP3 and WAV are requested directly at 24kHz. There is no retry, redirect following, SDK global-key mutation or fallback. All independent TTS fields empty still select the unchanged legacy Qwen path.

Only ws/wss URLs without userinfo, query, fragment or control characters are accepted. Use WSS remotely; WS is for trusted local endpoints only. Qwen uses the existing 60-second total deadline and 10-second socket timeout, a 24 MiB received-wire budget, 2 MiB per-frame/text-message limit and 16 MiB audio limit. Oversized frame lengths are rejected before payload allocation; fragmented messages remain bounded. Connections close on every outcome. Calls refuse to connect if websocket-client trace logging is enabled, rather than risk credential logging or mutate global logging settings. `websocket-client` is a direct dependency; the adapter does not import the DashScope synthesizer. Offline tests verify this protocol; live Qwen acceptance remains an operator-owned step.

## API and Validation

`POST /api/tts` remains `{text, voice?, format: "mp3" | "wav"}`, with at most 800 text characters. Omitted voice uses the first configured voice; unlisted voices are rejected. Audio responses include `X-TTS-Provider`, `X-TTS-Model`, `X-TTS-Voice`, timing/size/digest metadata and generic `tts.mp3`/`tts.wav` filenames. Legacy Qwen responses additionally retain compatibility headers.

Volcengine appends `/tts/unidirectional`, sends `X-Api-Key` and `X-Api-Resource-Id`, and posts `req_params{text,speaker,audio_params{format,sample_rate:24000}}`. NDJSON requires nonempty valid audio and terminal code `20000000`. Documented `data:null` / sentence objects are skipped, never mistaken for audio. Embedded HTTP-200 errors, truncation and invalid JSON/base64/types produce sanitized 502 errors. The HTTP Chunked documentation recommends PCM to avoid repeated streaming WAV headers. WAV therefore requests `pcm` and uses standard-library 24kHz mono int16 wrapping. Raw PCM has no magic prefix; validation relies on protocol success, nonempty size-limited data and int16 alignment, not prefix-based format detection.

OpenAI appends `/audio/speech`, sends its own Bearer credential and model/input/voice/response_format. Minimal MP3-frame/WAV validation rejects HTML/JSON error bodies masquerading as audio. PCM checks cover nonempty int16 alignment only; release acceptance must validate actual decoding. Limits: 24 MiB response, 2 MiB NDJSON line, 16 MiB audio, 10-second connect/read timeout and 60-second total reading deadline.

`GET /api/status` adds `tts` with provider, base_host, model, key_configured, configured, voices, default_voice and a fixed safe error where needed. No keys, resource identifiers or raw upstream bodies are exposed. Top-level tts_model reflects effective TTS. The UI uses `tts.configured`, renders voice labels as text nodes, preserves clone selection on refresh and leaves the realtime voice dropdown unchanged.

For explicit configuration, `chatenv --home <isolated-home> test -t chatvoice -I` reuses the already-resolved EnvStore, synthesizes a short test sentence and discards audio without importing the web app/GPU. Failures return nonzero; existing notes/title probes remain intact. This command makes real endpoint requests: operators must confirm authorization and billing first. Automated tests mock network and isolate HOME/CHATARCH_HOME/TMPDIR.

## Release and Rollback

Review the local wheel, mock tests, CLI trees and strict docs build before the deployment owner performs real synthesis/decoder/browser playback acceptance, backups and rollback. This hotfix does not deploy or alter accounts or billing settings. Preserve prior configuration securely. Legacy TTS rollback requires clearing all six independent fields and retaining a valid legacy Token Plan key, not a partial configuration. Do not change ASR, realtime, text, VoiceClone or database configuration.
