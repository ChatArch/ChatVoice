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

Recent recorder UX includes pause-time ASR window finalization, direct `刷新标题` / `新建` header controls for mobile use, a compact meeting `#` tag picker, a clearer toolbar, and a confirmation guard before clearing a meeting with existing content. Meetings default to no tags and can be classified with `thought` / `diary` presets plus repeated custom tags. The meeting recorder saves text, tags, and summaries only; original recording files are not saved locally or on the server. See [Recording Storage Boundary](docs/recording-storage.en.md).

Documentation entry: <https://arch.gh.wzhecnu.cn/ChatVoice/en/>

## Login Backend and Frontend Boundary

ChatVoice depends on the authentication/session core from `ChatLogin>=0.1.1,<0.2.0` while retaining its original HTML, CSS, vanilla JavaScript, and login/guest dialog. It does not inject ChatLogin's default templates. A host adapter reuses the existing `accounts` and `auth_sessions` tables, account IDs, PBKDF2 material, and cookie. No second user database or forced password reset is introduced.

Existing `/api/auth/*` endpoints and JSON fields remain compatible. Existing accounts map to ordinary users, not a new Web Admin. ChatVoice retains meeting/conversation owner checks and API-token scopes. Guest records remain in browser IndexedDB and are not automatically uploaded. Package release is separate from production deployment, restart, or data migration.

## Quick start from PyPI

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.1.15"

chatvoice --tree
chatvoice --tree-brief
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

The packaged service defaults to SQLite WAL under:

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

Use one service process with SQLite (`--workers 1`). Back up and move data with the CLI single-file dump/restore commands. There is no `DATABASE_URL` ChatVoice setting in the packaged storage layer. Future high-concurrency Postgres/MySQL support is a separate storage-layer migration.


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

The backend SQLite `meetings.sqlite3` currently contains `accounts`, `auth_sessions`, `api_tokens`, `meeting_records`, and `conversation_records`. Transcripts, summary content, meeting tags, and realtime messages are stored as JSON strings; raw audio is not stored in the backend database. Guest mode still uses browser IndexedDB for local meeting text, tags, and summaries, not recording chunks. The packaged service supports SQLite WAL + one service process; move data with the CLI single-file dump/restore commands. Future high-concurrency Postgres/MySQL support is a separate storage-layer migration. See [Runtime Layout and Data Structure](docs/runtime-layout.en.md) and [Recording Storage Boundary](docs/recording-storage.en.md).

## CLI contract

```bash
chatvoice --tree
chatvoice --tree-brief
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
| Understand recording storage boundaries | `docs/recording-storage.en.md` |
| Check implemented commands | `docs/cli-tree.en.md` |
| Check package capabilities and boundaries | `docs/capability-map.en.md` |
| Call package behavior directly from Python | `docs/interface-tree.md` |

## Development notes

See `DEVELOP.md` and `AGENTS.md` before expanding the package.
