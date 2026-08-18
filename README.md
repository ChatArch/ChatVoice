# ChatVoice / Speakr Voice Workspace

ChatVoice is the ChatArch repository and Python package shell for the Speakr voice workspace: a FastAPI + browser product with realtime meeting transcription, local audio capture, AI notes, TTS, and full-duplex voice conversation. The deployed product uses Speakr as its canonical public service, while `ChatVoice` is the package, CLI, and repository name.

Public site: [https://speakr.public.wzhecnu.cn/](https://speakr.public.wzhecnu.cn/)

Repository: [https://github.com/ChatArch/ChatVoice](https://github.com/ChatArch/ChatVoice)

PyPI package: [https://pypi.org/project/ChatVoice/](https://pypi.org/project/ChatVoice/)

Documentation: [https://arch.gh.wzhecnu.cn/ChatVoice/](https://arch.gh.wzhecnu.cn/ChatVoice/)

The former `qwen-audio-demo.public.wzhecnu.cn` entry is retired and returns HTTP 410.

## Features

- **语音合成 (TTS)**: server-side proxy for `qwen-audio-3.0-tts-plus`, returning playable MP3/WAV audio.
- **声音克隆**: server-side DashScope TTS v2 voice enrollment (`VoiceEnrollmentService`) creates reusable `voice_id` values; the browser never sees provider credentials.
- **实时对话**: 独立的豆包式语音对话页；browser WebSocket -> FastAPI proxy -> Qwen Realtime，支持服务端模型列表、VAD、流式文字、24 kHz PCM 播放、自然打断、对话历史和 Markdown 导出。
- **会议录音首页**: mobile-first recording surface with live transcript, waveform, pause/resume, finish, and local audio download.
- **Bounded local archive**: MediaRecorder emits one-second chunks into browser-only IndexedDB; the full Blob is assembled only when the user requests a download.
- **语音转写**: the recorder streams microphone PCM16 to the ASR WebSocket and appends normalized final segments to the timeline.
- **API-first ASR**: production ASR is designed around `api-server`, where the ChatVoice backend calls either a managed ASR API or a self-hosted GPU ASR server. `stub-local` remains available for contract smoke, and `funasr-gpu` / `funasr-cpu` remain compatibility channels.
- **Realtime ASR WebSocket**: `WS /ws/asr/stream` accepts continuous PCM16 microphone frames and returns cumulative revision events. Long recordings transparently roll a bounded context window while confirmed text continues to grow.
- **会议纪要**: final transcript segments can be sent to a server-side Qwen-compatible model for summary, action items, risks, and open questions.
- **双模式会议历史**: guests keep meeting text and summaries only in browser IndexedDB; signed-in accounts sync records through authenticated server storage.
- **0.1 API 访问**: signed-in users can generate one-time-visible API tokens from the web settings panel; `chatvoice data ...` can then read meetings, summaries, and realtime conversations from a running service.
- **受邀账号登录**: public registration is disabled. Accounts are provisioned by `chatvoice accounts add`; passwords use salted PBKDF2 hashes, sessions use HttpOnly cookies, and record writes require CSRF tokens.

## Security model

- The browser never receives or stores provider credentials.
- Set provider credentials only in server-side environment/config storage; never expose them to the browser.
- Do not commit real env files, model caches, probe output, audio files, runtime logs, or generated API token values.
- Guest meeting and conversation records never enter the server database. Audio/transcript data still passes through ASR/summary or Realtime services while a request is processed.
- Raw recording blobs are not uploaded by the meeting-history feature; the current page keeps them only for local download.
- Realtime history stores text, model, and voice only; raw conversation audio is never written to history storage.
- API tokens are stored server-side as hashes. Token values are displayed only once on creation.

## Quick start from the released package

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.1.1"

chatvoice --tree
chatvoice service plan --ensure-dirs --json
chatvoice serve app --host 127.0.0.1 --port 18087
```

Open:

```text
http://127.0.0.1:18087/
```

For a credential-free wiring smoke, use:

```bash
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

For a real ASR backend, keep credentials server-side and call an API provider:

```bash
export CHATVOICE_ASR_CHANNEL=api-server
export CHATVOICE_ASR_API_URL="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.
chatvoice serve app --host 127.0.0.1 --port 18087
```

Meeting summary generation is also a server-side model boundary: configure the notes model/provider in server-side environment or config storage, and let the browser/API read only the saved summary text.

## Fresh account, browser, token, and data flow

Create one invited account in the same local runtime database used by the service:

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts add person@example.com --display-name "Person" --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice accounts list --json
```

Then:

1. open the web service;
2. log in with the invited account;
3. create or open a meeting and generate its summary;
4. open **识别设置 → API Token → 生成 Token**;
5. copy the token immediately; it is only shown once.

The same token lifecycle is available from CLI after the service is running:

```bash
chatvoice tokens create --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name automation --json
chatvoice tokens list --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --json
```

Use the token with the data API/CLI:

```bash
read -r -s CHATVOICE_DATA_READ
export CHATVOICE_DATA_READ
chatvoice data meetings --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversations --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
```

## Database and concurrency

The packaged v0.1.1 web app defaults to SQLite WAL at:

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

Use one service process (`--workers 1`) with SQLite. For high-concurrency production, migrate the storage layer to Postgres/MySQL before scaling workers or nodes. An external database URL setting is detected by `chatvoice doctor` / `chatvoice service plan`, but the v0.1.1 packaged legacy storage layer still supports SQLite only.

## API surface

- `GET /api/status`: redacted backend status, models, ASR channels, and route shapes.
- `POST /api/tts`: JSON `{text, voice, format}` -> `audio/mpeg` or `audio/wav`.
- `POST /api/voice-cloning/create`: JSON `{audio_url, prefix, target_model, language_hints}` -> server-created `voice_id`.
- `GET /api/voice-cloning/list`: list server-side voice enrollment ids by prefix.
- `GET /api/asr/channels`: available ASR channels.
- `POST /api/asr`: programmatic/smoke multipart upload endpoint with `channel=api-server|funasr-gpu|funasr-cpu|stub-local`.
- `WS /ws/asr/stream`: bounded PCM16 stream used by the recorder.
- `GET /api/realtime/models`: Realtime models currently exposed by the configured account.
- `WS /ws/realtime?model=<id>`: browser-to-backend Realtime proxy.
- `POST /api/meeting-notes/polish`: Qwen-compatible chat completion endpoint for transcript polish + realtime summary structure.
- `POST /api/auth/register`: intentionally returns `403`; self-registration is disabled.
- `POST /api/auth/login`, `GET /api/auth/session`, `POST /api/auth/logout`: invited-account session lifecycle.
- `GET|PUT|DELETE /api/meetings[/<id>]`: authenticated meeting record storage. Writes require the session CSRF token.
- `GET|PUT|DELETE /api/conversations[/<id>]`: authenticated text-only Realtime conversation storage. Writes require the session CSRF token.
- `GET|POST /api/tokens`, `DELETE /api/tokens/<id>`: signed-in session token management.
- `GET /api/data/meetings[/<id>]`, `GET /api/data/conversations[/<id>]`: bearer-token data export for meetings, summaries, and realtime conversations.

## Verification

```bash
python -m pytest -q
PYTHONPATH=src python -m chatvoice.cli --tree
python -m mkdocs build --strict
python -m build
python -m twine check dist/*
```
