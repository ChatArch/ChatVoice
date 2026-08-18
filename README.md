# ChatVoice / Speakr Voice Workspace

ChatVoice is the ChatArch repository and Python package shell for the Speakr voice workspace: a FastAPI + browser product with realtime meeting transcription, local audio capture, AI notes, TTS, and full-duplex voice conversation. The git history retains its early Qwen Audio Demo origin; the deployed product uses Speakr as its canonical domain.

Public site: [https://speakr.public.wzhecnu.cn/](https://speakr.public.wzhecnu.cn/)

Repository: [https://github.com/ChatArch/ChatVoice](https://github.com/ChatArch/ChatVoice)

PyPI package: [https://pypi.org/project/ChatVoice/](https://pypi.org/project/ChatVoice/)

Documentation: [https://arch.gh.wzhecnu.cn/ChatVoice/](https://arch.gh.wzhecnu.cn/ChatVoice/)

The former `qwen-audio-demo.public.wzhecnu.cn` entry is retired and returns HTTP 410.

## Features

- **语音合成 (TTS)**: server-side proxy for `qwen-audio-3.0-tts-plus`, returning playable MP3/WAV audio.
- **声音克隆**: server-side DashScope TTS v2 voice enrollment (`VoiceEnrollmentService`) creates reusable `voice_id` values; the browser never sees the API key.
- **实时对话**: 独立的豆包式语音对话页；browser WebSocket -> FastAPI proxy -> Qwen Realtime，支持服务端模型列表、VAD、流式文字、24 kHz PCM 播放、自然打断、对话历史和 Markdown 导出。
- **会议录音首页**: a mobile-first recording surface with live transcript, waveform, pause/resume, finish, and local audio download.
- **Bounded local archive**: MediaRecorder emits one-second chunks into a browser-only IndexedDB store; the full Blob is assembled only when the user requests a download, with an explicit in-memory fallback if browser storage fails.
- **语音转写**: the recorder streams microphone PCM16 to the existing ASR WebSocket and appends normalized final segments to the timeline.
- **API-first ASR**: production ASR is designed around `api-server`, where the ChatVoice backend calls either a managed ASR API or a self-hosted GPU ASR server. `stub-local` remains available for contract smoke, and `funasr-gpu` / `funasr-cpu` remain compatibility channels.
- **Realtime ASR WebSocket**: `WS /ws/asr/stream` accepts continuous PCM16 microphone frames and returns cumulative revision events. Long recordings transparently roll a bounded context window while confirmed text continues to grow.
- **会议纪要**: final transcript segments can be sent to a server-side Qwen-compatible model for summary, action items, risks, and open questions.
- **双模式会议历史**: guests keep meeting text and summaries only in browser IndexedDB; signed-in accounts sync records through authenticated server storage.
- **受邀账号登录**: public registration is disabled. Accounts are provisioned from the server CLI; passwords use salted PBKDF2 hashes, sessions use HttpOnly cookies, and record writes require CSRF tokens.
- **Focused product UI**: 一级工作区为 `会议记录 / 声音工作室 / 实时对话`；会议内部保留 `文字记录 / 实时摘要` 两个内容标签。

## Security model

- The browser never receives or stores the Qwen API key.
- Set provider keys only in server-side environment/config storage; never expose them to the browser.
- Optional host-local env-file loading is supported, but public docs use placeholders instead of secret-bearing file names.
- Do not commit real env files, model caches, probe output, audio files, or runtime logs.
- Guest meeting and conversation records never enter the server database. Audio/transcript data still passes through the ASR/summary or Realtime service while a request is processed.
- Raw recording blobs are not uploaded by the meeting-history feature; the current page keeps them only for local download.
- Realtime history stores text, model and voice only; raw conversation audio is never written to history storage.

## Quick start from the released package

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.0.2"

chatvoice --tree
chatvoice service plan --ensure-dirs --json
chatvoice serve app --host 127.0.0.1 --port 18087
```

Open:

```text
http://127.0.0.1:18087/
```

For a real ASR backend, keep credentials server-side and call an API provider:

```bash
export CHATVOICE_ASR_CHANNEL=api-server
<ASR_API_URL_SETTING>="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.
chatvoice serve app --host 127.0.0.1 --port 18087
```

For a credential-free wiring smoke, use:

```bash
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```


## Optional env file for Qwen-compatible APIs

```bash
# Configure a host-local provider-env file through your deployment secret store.
# Keep file names and values outside public docs and Git.
chatvoice serve app --host 127.0.0.1 --port 18087
```

## ASR API server and optional local GPU mode

Recommended production shape:

```bash
export CHATVOICE_ASR_CHANNEL=api-server
<ASR_API_URL_SETTING>="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.
chatvoice serve app --host 127.0.0.1 --port 18087
```

The ASR service can be a managed API or a self-hosted GPU server. ChatVoice sends multipart field `file` and reads `corrected_text`, `text`, `transcript`, `raw_text`, `data.text`, or `result.text` from the JSON response.

`funasr-gpu` remains available as a compatibility channel when the web service and GPU runtime intentionally live on the same host. It is no longer the recommended default packaging model because separating the GPU worker behind an API server is easier to scale, restart, and secure.

Default runtime paths are under `<chatarch-home>/chatvoice/`; model caches are under `<chatarch-home>/chatvoice/model-cache/` unless overridden.

## Database and concurrency

The packaged v0.0.2 web app defaults to SQLite WAL at:

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

Use one service process (`--workers 1`) with SQLite. For high-concurrency production, migrate the storage layer to Postgres/MySQL before scaling workers or nodes. an external database URL setting is detected by `chatvoice doctor` / `chatvoice service plan`, but the v0.0.2 packaged legacy storage layer still supports SQLite only.

## API surface

- `GET /api/status`: redacted backend status, models, ASR channels, and route shapes.
- `POST /api/tts`: JSON `{text, voice, format}` -> `audio/mpeg` or `audio/wav`.
- `POST /api/voice-cloning/create`: JSON `{audio_url, prefix, target_model, language_hints}` -> server-created `voice_id`.
- `GET /api/voice-cloning/list`: list server-side voice enrollment ids by prefix.
- `GET /api/asr/channels`: available ASR channels; packaged default is `api-server` when the ASR API URL setting is configured, otherwise `stub-local`.
- `POST /api/asr`: programmatic/smoke multipart upload endpoint with `channel=api-server|funasr-gpu|funasr-cpu|stub-local` and `correct=true|false`; not the browser ASR product flow.
- `WS /ws/asr/stream`: bounded PCM16 stream used by the recorder. Results include `stream.revision`, `stream.revision_scope=window`, `stream.window_index`, `stream.replace=true`, and `stream.final`; clients replace only the current rolling window and append confirmed windows.
- `GET /api/realtime/models`: Realtime models currently exposed by the configured account; the browser selector is populated from this list.
- `WS /ws/realtime?model=<id>`: browser-to-backend Realtime proxy; upstream events are normalized into `demo_event=transcript.delta` for the Realtime board.
- `POST /api/meeting-notes/polish`: Qwen-compatible chat completion endpoint for transcript polish + realtime summary structure.
- `POST /api/auth/register`: intentionally returns `403`; self-registration is disabled.
- `POST /api/auth/login`, `GET /api/auth/session`, `POST /api/auth/logout`: invited-account session lifecycle.
- `GET|PUT|DELETE /api/meetings[/<id>]`: authenticated meeting record storage. Writes require the session CSRF token.
- `GET|PUT|DELETE /api/conversations[/<id>]`: authenticated text-only Realtime conversation storage. Writes require the session CSRF token.

### Public ASR stream limits

`/ws/asr/stream` applies explicit recording-segment policies:

- accepted sample rates are `8000`, `16000`, `24000`, and `48000` Hz;
- one websocket audio frame is capped at 256 KiB of PCM16 data;
- one JSON/base64 frame is capped at 384 KiB;
- guest mode allows 10 active recording minutes per segment; signed-in mode allows 2 active hours per segment;
- pause time does not consume the segment allowance, and an existing meeting can start another segment later;
- recognition context rolls about every 42–45 seconds, so GPU inference and memory stay bounded during a multi-hour meeting;
- original MediaRecorder chunks are written to browser IndexedDB once per second instead of accumulating the whole recording in JavaScript memory;
- reaching a segment limit finalizes the last window and returns a normal `done` event instead of failing the recording;
- each receive cycle processes at most two ASR chunks and reports backpressure if more decoded audio is queued;
- per-chunk temporary WAV/upload files under `playground/asr-temp/` are cleaned after each ASR attempt.

### Manage invited accounts

Run this only from the server shell. The password is prompted twice and is never passed as a command-line argument:

```bash
python3 scripts/manage_accounts.py add person@example.com --display-name "Person"
python3 scripts/manage_accounts.py list
```

The command uses `MEETING_DB_PATH` when set, otherwise the same default `playground/meetings.sqlite3` database as the service.

## Verification

```bash
python3 scripts/check_ui_contract.py
node scripts/check_transcript_state_cases.js
python3 scripts/check_transcript_extraction.py
python3 scripts/check_asr_contract.py
python3 scripts/check_asr_gpu_contract.py
python3 scripts/check_meeting_storage_contract.py
python3 scripts/smoke_asr_api.py --port 18097
python3 scripts/check_meeting_e2e.py --base-url http://127.0.0.1:18087
```

`smoke_demo.py` also exercises `/api/status`, `/api/tts`, and `/ws/realtime`, but it requires a valid server-side Token Plan key:

```bash
python3 scripts/smoke_demo.py --port 18087
```

Browser-side regression helpers are available for manual dogfood:

```javascript
window.__demoInjectAsrScenario()
window.__demoInjectSummary()
window.__demoGetState()
```

## Known boundaries

- The Token Plan TTS route is not OpenAI `/audio/speech`; this demo uses the official Token Plan WebSocket SDK path for TTS.
- `qwen-audio-3.0-realtime-plus` is a realtime voice conversation model, not a dedicated pure-ASR model.
- Voice cloning requires a reference audio URL that DashScope can fetch from the server side.
- GPU FunASR first-run model download/warm-up can be slow; keep `stub-local` for fast public smoke and CI-like contract checks.
