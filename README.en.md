<div align="center">
    <a href="https://pypi.python.org/pypi/ChatVoice">
        <img src="https://img.shields.io/pypi/v/ChatVoice.svg" alt="PyPI version" />
    </a>
    <a href="https://github.com/ChatArch/ChatVoice/actions/workflows/ci.yml">
        <img src="https://github.com/ChatArch/ChatVoice/actions/workflows/ci.yml/badge.svg" alt="Tests" />
    </a>
    <a href="https://arch.gh.wzhecnu.cn/ChatVoice/">
        <img src="https://img.shields.io/badge/docs-mkdocs-blue.svg" alt="Documentation" />
    </a>
</div>

<div align="center">

[English](README.en.md) | [简体中文](README.md)
</div>

# ChatVoice

ChatArch voice recording, transcription, and meeting-notes toolkit. ChatVoice packages the Speakr FastAPI + browser service so a release can be installed, started, account-provisioned, and queried from the Python package.

Recent recorder UX includes pause-time ASR window finalization, direct `刷新标题` / `新建` header buttons for mobile use, a clearer toolbar, and a confirmation guard before clearing a meeting with existing content. Original audio is not saved by default: logged-in accounts sync text, summaries, and metadata only; users must opt into `保存音频` to keep browser-local audio chunks for download.

Documentation entry: <https://arch.gh.wzhecnu.cn/ChatVoice/en/>

## Quick start from PyPI

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.1.5"

chatvoice --tree
chatvoice service plan --ensure-dirs --json
chatvoice serve app --host 127.0.0.1 --port 18087
```

Open:

```text
http://127.0.0.1:18087/
```

## Fresh account and data flow

Create a managed account in the packaged runtime database:

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts add person@example.com --display-name "Person" --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice accounts list --json
```

Log in through the browser, create a meeting, generate a summary, then create a one-time-visible API token from **Settings → API Token**. The CLI can also create/list/revoke tokens against a running service:

```bash
chatvoice tokens create --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name automation --json
chatvoice tokens list --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --json
```

Use the token to read meetings, summaries, and realtime conversations:

```bash
read -r -s CHATVOICE_DATA_READ
export CHATVOICE_DATA_READ
chatvoice data meetings --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversations --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
```

## ASR provider model

Production ASR should run as an API provider. The provider can be a managed API or a self-hosted GPU ASR server:

```bash
export CHATVOICE_ASR_CHANNEL=api-server
export CHATVOICE_ASR_API_URL="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.
chatvoice serve app --host 127.0.0.1 --port 18087
```

For credential-free wiring smoke:

```bash
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

`funasr-gpu` and `funasr-cpu` remain compatibility channels, but the recommended production boundary is to keep GPU runtime behind an ASR API server and let ChatVoice call it over HTTP.

Meeting summary generation is also a server-side model boundary: configure the notes model/provider in server-side environment or config storage, and let the browser/API read only the saved summary text.

## Database and concurrency

v0.1.5 defaults to SQLite WAL under:

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

Use one service process with SQLite (`--workers 1`). High-concurrency production should migrate the storage layer to Postgres/MySQL before scaling workers or nodes. An external database URL setting is detected in `chatvoice doctor` / `chatvoice service plan`, but the v0.1.5 packaged legacy storage layer still supports SQLite only.


## Runtime layout and data structure

After `pip install`, package code lives under the active Python `site-packages/chatvoice/`, and the CLI entry point is the matching `bin/chatvoice`; production should use a dedicated venv. Runtime state does not live in the source checkout. The runtime root resolves in this order: `CHATVOICE_RUNTIME_ROOT`, `CHATVOICE_HOME`, `CHATARCH_HOME/chatvoice`, then `~/.chatarch/chatvoice`. Default layout:

```text
~/.chatarch/chatvoice/
├── data/meetings.sqlite3
├── logs/
├── run/
├── temp/asr/
└── model-cache/
```

The backend SQLite `meetings.sqlite3` currently contains `accounts`, `auth_sessions`, `api_tokens`, `meeting_records`, and `conversation_records`. Transcripts, summary content, and realtime messages are stored as JSON strings; raw audio is not stored in the backend database. Guest mode still uses browser IndexedDB for local meetings and recording chunks. High-concurrency Postgres/MySQL migration is tracked as TODO; `0.1.5` still supports SQLite WAL + one service process only. See [Runtime Layout and Data Structure](docs/runtime-layout.en.md).

## CLI contract

```bash
chatvoice --tree
chatvoice paths --json
chatvoice doctor --json
chatvoice accounts list --json
chatvoice asr channels --json
chatvoice health status --url http://127.0.0.1:18087 --json
curl -s http://127.0.0.1:18087/api/heartbeat | python -m json.tool
```

`GET /api/heartbeat` reports lightweight service/database/ASR health, including `asr.status` (`ready`, `processing`, or `degraded`), FunASR model warm-up state, and the most recent ASR success/failure metadata. The browser uses the same heartbeat plus WebSocket `asr.stream.processing` / `asr.stream.heartbeat` events to show model-loading or recognition failures instead of silently recording with no transcript output.

The CLI is a thin adapter over importable Python APIs. See `docs/interface-tree.md` for the function mapping.

## Documentation

Choose documentation by scenario:

| Scenario | Document |
| --- | --- |
| Install from PyPI and start the service | `docs/deployment.en.md` |
| Generate tokens and read data APIs | `docs/api-access.en.md` |
| Check implemented commands | `docs/cli-tree.en.md` |
| Check package capabilities and boundaries | `docs/capability-map.en.md` |
| Call package behavior directly from Python | `docs/interface-tree.md` |

## Development notes

See `DEVELOP.md` and `AGENTS.md` before expanding the package.
