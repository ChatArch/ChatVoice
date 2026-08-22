# ChatVoice / Speakr Voice Workspace

ChatVoice is the ChatArch repository and Python package shell for the Speakr voice workspace: a FastAPI + browser product with realtime meeting transcription, AI notes, TTS, and full-duplex voice conversation. The deployed product uses Speakr as its canonical public service, while `ChatVoice` is the package, CLI, and repository name.

Public site: [https://speakr.public.wzhecnu.cn/](https://speakr.public.wzhecnu.cn/)

Repository: [https://github.com/ChatArch/ChatVoice](https://github.com/ChatArch/ChatVoice)

PyPI package: [https://pypi.org/project/ChatVoice/](https://pypi.org/project/ChatVoice/)

Documentation: [https://arch.gh.wzhecnu.cn/ChatVoice/](https://arch.gh.wzhecnu.cn/ChatVoice/)

The former `qwen-audio-demo.public.wzhecnu.cn` entry is retired and returns HTTP 410.

## Features

- **语音合成 (TTS)**: server-side proxy for `qwen-audio-3.0-tts-plus`, returning playable MP3/WAV audio when the model provider key is configured.
- **本地声音复刻**: Voice Studio is one unified panel: choose **系统音色** (built-in TTS voices) or **我的复刻声音** (upload/record an authorized reference audio sample) and share the same text box. The clone path runs a one-shot VoiceClone/IndexTTS-2.5 job through a local sidecar; the browser receives a playable/downloadable result for the current job only. Within a session the reference audio is kept so the cloned voice can be reused for new text until the page is left. No voice profile or generated-audio history is saved. See [声音复刻使用指南](docs/voice-cloning.md).
- **实时对话**: 独立的豆包式语音对话页；browser WebSocket -> FastAPI proxy -> Qwen Realtime，支持服务端模型列表、VAD、流式文字、24 kHz PCM 播放、自然打断、对话历史和 Markdown 导出。
- **会议记录首页**: mobile-first recording surface with live transcript, waveform, pause/resume, and finish flow. Audio is used for realtime transcription; the product saves text and summaries, not recording files.
- **暂停整理**: pausing a recording commits the current ASR window so pending live/rewrite text can be finalized before continuing.
- **标题刷新与新建快捷入口**: the recorder header includes direct `刷新标题` and `新建` buttons for full-session title regeneration and faster mobile topic creation.
- **清空防误触**: resetting a meeting with existing text/summary state requires confirmation.
- **原始录音不保存**: 当前会议记录功能不提供“保存录音”或“下载录音”。服务器只保存文字、摘要和会议元数据；访客模式只在浏览器保存文字/摘要。详见 [录音保存边界](docs/recording-storage.md)。
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
- Raw meeting recordings are not saved by the meeting recorder: no backend raw-audio database/object store, no browser-local recording chunks, and no recording download endpoint in the current version.
- Realtime history stores text, model, and voice only; raw conversation audio is never written to history storage.
- API tokens are stored server-side as hashes. Token values are displayed only once on creation.

## Quick start from the released package

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.1.8"

chatvoice --tree
chatvoice --tree-brief
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

The packaged v0.1.8 web app defaults to SQLite WAL at:

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

Use one service process (`--workers 1`) with SQLite. For high-concurrency production, migrate the storage layer to Postgres/MySQL before scaling workers or nodes. An external database URL setting is detected by `chatvoice doctor` / `chatvoice service plan`, but the v0.1.8 packaged legacy storage layer still supports SQLite only.


## 运行目录与数据结构

`pip install` 后代码安装在当前 Python 环境的 `site-packages/chatvoice/`，CLI 在对应环境的 `bin/chatvoice`；生产建议使用独立 venv。运行数据不写入源码目录，默认 root 解析顺序是 `CHATVOICE_RUNTIME_ROOT`、`CHATVOICE_HOME`、`CHATARCH_HOME/chatvoice`、`~/.chatarch/chatvoice`。默认结构：

```text
~/.chatarch/chatvoice/
├── data/meetings.sqlite3
├── logs/
├── run/
├── temp/asr/
└── model-cache/
```

后端 SQLite `meetings.sqlite3` 目前包含 `accounts`、`auth_sessions`、`api_tokens`、`meeting_records`、`conversation_records`。转写、summary、实时对话消息以 JSON 字符串保存；原始音频不进后端数据库。访客模式仍使用浏览器 IndexedDB 保存本地会议文字和摘要，不保存录音分片。高并发 Postgres/MySQL 迁移列入 TODO，当前 `0.1.8` 仍只支持 SQLite WAL + 单服务进程。详见 [运行目录与数据结构](docs/runtime-layout.md) 和 [录音保存边界](docs/recording-storage.md)。

## API surface

`GET /api/heartbeat` 是轻量服务心跳，用来判断 Web 服务、SQLite 只读探测和 ASR 状态是否正常；`asr.status` 会返回 `ready`、`processing` 或 `degraded`，并包含 FunASR 模型是否已热、最近一次识别成功/失败、耗时和输出长度。录音 WebSocket 也会发 `asr.stream.processing` / `asr.stream.heartbeat`，前端会显示“模型加载中/识别处理中/失败原因”，不再静默录音无文字。

- `GET /api/status`: redacted backend status, models, ASR channels, sidecar configuration, and route shapes.
- `GET /api/heartbeat`: lightweight service/database/ASR heartbeat with model warm-up, processing, and recent error/success state.
- `POST /api/tts`: JSON `{text, voice, format}` -> `audio/mpeg` or `audio/wav`.
- `GET /api/voice-clone/status`: redacted local VoiceClone sidecar status.
- `POST /api/voice-clone/jobs`: authenticated multipart `{text, lang, duration_factor, reference_audio}` -> one-shot local clone job.
- `GET /api/voice-clone/jobs/<id>`: authenticated job polling with progress/stage/ETA.
- `GET /api/voice-clone/jobs/<id>/audio`: authenticated generated audio download/preview.
- `POST /api/voice-cloning/create`: legacy DashScope enrollment endpoint for reusable `voice_id` creation; not the primary browser Voice Studio flow.
- `GET /api/voice-cloning/list`: legacy list of server-side voice enrollment ids by prefix.
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
PYTHONPATH=src python -m chatvoice.cli --tree-brief
python -m mkdocs build --strict
python -m build
python -m twine check dist/*
```
