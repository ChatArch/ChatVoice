# Deployment and Startup

This page explains how to run a ChatVoice / Speakr service from the released Python package in v0.1.4: install, create an account, start the service, generate an API token, and read meeting/summary data.

## Minimal install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.1.4"
```

Read back the real CLI tree and runtime paths first:

```bash
chatvoice --tree
chatvoice paths --json
chatvoice service plan --ensure-dirs --json
```

After `pip install`, package code lives under the active Python `site-packages/chatvoice/`, and the CLI entry point is the matching `bin/chatvoice`; production should use a dedicated venv. Runtime data is not written to the source checkout.

Default runtime state lives under ChatArch home:

```text
<chatarch-home>/chatvoice/
├── data/          # default SQLite database
├── logs/
├── run/
├── temp/
│   └── asr/
└── model-cache/
```

The runtime root resolves in this order: `CHATVOICE_RUNTIME_ROOT`, `CHATVOICE_HOME`, `CHATARCH_HOME/chatvoice`, then `~/.chatarch/chatvoice`. `temp/asr` holds ASR temporary files; see [Runtime Layout and Data Structure](runtime-layout.md) for the full layout and schema.

## Create an invited account

After installing `ChatVoice[web]`, no source-tree script is required. Use the packaged CLI. Passwords are read from environment variables only:

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts add person@example.com --display-name "Person" --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice accounts list --json
```

## Start the web service

Credential-free / GPU-free contract smoke:

```bash
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

Open:

```text
http://127.0.0.1:18087/
```

For production, put the service behind a controlled reverse proxy. API keys stay server-side and must not appear in browser code, command argv, Git, logs, or public docs.

## ASR provider: API first

The recommended production shape in v0.1.4 is **ChatVoice calls ASR through an API provider**. That provider can be:

- a managed cloud ASR API with an API key;
- a self-hosted GPU ASR server exposing HTTP;
- an internal GPU node fronted by a private route or reverse proxy.

Configure it like this:

```bash
export CHATVOICE_ASR_CHANNEL=api-server
export CHATVOICE_ASR_API_URL="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.
chatvoice serve app --host 127.0.0.1 --port 18087
```

The browser **Settings → Server-side API Key** panel shows whether `CHATVOICE_ASR_API_KEY`, the summary/realtime model key, and the voice-cloning key are configured. It displays status only and never stores raw key values in the browser. Model/summary keys belong in server-side protected environment or config storage, such as `DASHSCOPE_API_KEY` / `OPENAI_API_KEY`.

ChatVoice sends uploaded audio to `CHATVOICE_ASR_API_URL` as multipart field `file` and reads `corrected_text`, `text`, `transcript`, `raw_text`, `data.text`, or `result.text` from the ASR JSON response.

`funasr-gpu` and `funasr-cpu` remain as compatibility channels, but they are not the recommended default deployment shape. For flexible operations, run the GPU runtime as a separate ASR API server and let ChatVoice call it through `api-server`.

Meeting summary generation is also a server-side model boundary: configure the notes model/provider in server-side environment or config storage, and let the browser/API read only the saved summary text.

## Generate a token and read data

After browser login, create a token from **Settings → API Token**. Token values are shown once. The CLI can also create tokens:

```bash
chatvoice tokens create --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name automation --json
```

Put the token into the environment variable selected by `--token-env`, then read meetings/summaries/conversations:

```bash
read -r -s CHATVOICE_DATA_READ
export CHATVOICE_DATA_READ
chatvoice data meetings --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversations --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
```

See [API Access](api-access.md) for details.

## Database and concurrency boundary

The v0.1.4 packaged web app uses SQLite WAL by default:

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

Core tables are `accounts`, `auth_sessions`, `api_tokens`, `meeting_records`, and `conversation_records`. Transcripts, summary content, and realtime messages are stored as JSON strings. Raw audio is not stored in the backend database. Guest-mode local records and recording chunks stay in browser IndexedDB.

This is suitable for one service process, light concurrency, and controlled internal use. The current boundary is:

- run `chatvoice serve app --workers 1`;
- do not run multiple workers/nodes writing the same SQLite file;
- high-concurrency production needs a storage-layer migration to Postgres/MySQL before scaling workers;
- an external database URL setting is detected by `doctor` / `service plan`, but the v0.1.4 packaged legacy storage layer still supports SQLite only.

Read back the effective plan:

```bash
chatvoice doctor --json
chatvoice service plan --json
```

## Health checks

```bash
chatvoice health status --url http://127.0.0.1:18087 --json
curl -s http://127.0.0.1:18087/api/heartbeat | python -m json.tool
```

Starting in `0.1.4`, the lightweight heartbeat separates “web service down”, “ASR is cold-starting/processing”, and “ASR recently failed”:

- `ok`: whether the web service, read-only database probe, and ASR state are usable.
- `asr.status`: `ready`, `processing`, or `degraded`.
- `asr.funasr_model_warm`: whether the FunASR GPU model is loaded in-process; the first cold start can take about one minute.
- `asr.recent.last_success_at` / `last_error_at`: most recent ASR success/failure timestamps.
- `asr.recent.last_elapsed_ms` / `last_text_chars`: most recent ASR latency and output length.

The recording WebSocket also emits `asr.stream.processing` and `asr.stream.heartbeat` while recognition is running. The browser shows model-loading/processing/failure state instead of silently recording with no transcript output.

Core service endpoints:

```text
GET /api/status
GET /api/heartbeat
GET /api/asr/channels
POST /api/asr
WS  /ws/asr/stream
GET /api/data/meetings
GET /api/data/conversations
```
