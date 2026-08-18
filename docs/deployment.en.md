# Deployment and Startup

This page explains how to run a ChatVoice / Speakr service from the released Python package in v0.1.0: install, create an account, start the service, generate an API token, and read meeting/summary data.

## Minimal install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.1.0"
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

The recommended production shape in v0.1.0 is **ChatVoice calls ASR through an API provider**. That provider can be:

- a managed cloud ASR API with an API key;
- a self-hosted GPU ASR server exposing HTTP;
- an internal GPU node fronted by a private route or reverse proxy.

Configure it like this:

```bash
export CHATVOICE_ASR_CHANNEL=api-server
<ASR_API_URL_SETTING>="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.
chatvoice serve app --host 127.0.0.1 --port 18087
```

ChatVoice sends uploaded audio to the ASR API URL setting as multipart field `file` and reads `corrected_text`, `text`, `transcript`, `raw_text`, `data.text`, or `result.text` from the ASR JSON response.

`funasr-gpu` and `funasr-cpu` remain as compatibility channels, but they are not the recommended default deployment shape. For flexible operations, run the GPU runtime as a separate ASR API server and let ChatVoice call it through `api-server`.

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

The v0.1.0 packaged web app uses SQLite WAL by default:

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

This is suitable for one service process, light concurrency, and controlled internal use. The current boundary is:

- run `chatvoice serve app --workers 1`;
- do not run multiple workers/nodes writing the same SQLite file;
- high-concurrency production needs a storage-layer migration to Postgres/MySQL before scaling workers;
- an external database URL setting is detected by `doctor` / `service plan`, but the v0.1.0 packaged legacy storage layer still supports SQLite only.

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
GET /api/data/meetings
GET /api/data/conversations
```
