# Deployment and Startup

This page explains how to run a ChatVoice / Speakr service from the released Python package in v0.0.2.

## Minimal install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.0.2"
```

Read back the real CLI tree and runtime paths first:

```bash
chatvoice --tree
chatvoice paths --json
chatvoice service plan --ensure-dirs --json
```

Default runtime state lives under ChatArch home:

```text
<chatarch-home>/chatvoice/
├── data/          # default SQLite database
├── logs/
├── run/
├── temp/
└── model-cache/
```

## Start the web service

```bash
chatvoice serve app --host 127.0.0.1 --port 18087
```

Open:

```text
http://127.0.0.1:18087/
```

For production, put the service behind a controlled reverse proxy. API keys stay server-side and must not appear in browser code, command argv, Git, logs, or public docs.

## ASR provider: API first

The recommended production shape in v0.0.2 is **ChatVoice calls ASR through an API provider**. That provider can be:

- a managed cloud ASR API with an API key;
- a self-hosted GPU ASR server exposing HTTP;
- an internal GPU node fronted by a private route or reverse proxy.

Configure it like this:

```bash
export CHATVOICE_ASR_CHANNEL=api-server
<ASR_API_URL_SETTING>="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.   # optional; never put this in argv
chatvoice serve app --host 127.0.0.1 --port 18087
```

ChatVoice sends uploaded audio to the ASR API URL setting as multipart field `file`. When a key is configured, it sends:

```text
Authorization: Bearer <server-side bearer token>
```

The JSON response parser looks for these fields first:

```text
corrected_text
text
transcript
raw_text
data.text
result.text
```

If the ASR API is not ready yet, use the contract-smoke provider:

```bash
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

`stub-local` proves upload, WebSocket, UI, storage, and service wiring only; it does not represent transcription quality.

## Optional local GPU compatibility channels

`funasr-gpu` and `funasr-cpu` remain as compatibility channels, but they are not the recommended default deployment shape. For flexible operations, run the GPU runtime as a separate ASR API server and let ChatVoice call it through `api-server`.

## Database and concurrency boundary

The v0.0.2 packaged web app uses SQLite WAL by default:

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

This is suitable for one service process, light concurrency, and controlled internal use. The current boundary is:

- run `chatvoice serve app --workers 1`;
- do not run multiple workers/nodes writing the same SQLite file;
- high-concurrency production needs a storage-layer migration to Postgres/MySQL before scaling workers;
- an external database URL setting is detected by `doctor` / `service plan`, but the v0.0.2 packaged legacy storage layer still supports SQLite only.

Read back the effective plan:

```bash
chatvoice doctor --json
chatvoice service plan --json
```

## Health checks

```bash
chatvoice health status --url http://127.0.0.1:18087 --json
```

Core service endpoints:

```text
GET /api/status
GET /api/asr/channels
POST /api/asr
WS  /ws/asr/stream
```
