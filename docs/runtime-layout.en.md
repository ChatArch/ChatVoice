# Runtime Layout and Data Structure

This page documents where `pip install "ChatVoice[web]==0.1.10"` installs code, where runtime data is written by default, and which data lives in SQLite versus the browser.

## Code install location

`pip install` installs a Python distribution; the source checkout is not required at runtime:

```text
<venv>/lib/pythonX.Y/site-packages/chatvoice/
<venv>/bin/chatvoice
```

Without a virtualenv, the location is controlled by the active Python `site-packages`. Production should use a dedicated venv, for example:

```text
/opt/chatvoice/.venv/lib/pythonX.Y/site-packages/chatvoice/
/opt/chatvoice/.venv/bin/chatvoice
```

## Default runtime root

ChatVoice resolves its state root in this order:

1. `CHATVOICE_RUNTIME_ROOT`
2. `CHATVOICE_HOME`
3. `CHATARCH_HOME/chatvoice`
4. `~/.chatarch/chatvoice`

Default layout:

```text
~/.chatarch/chatvoice/
├── data/
│   └── meetings.sqlite3
├── logs/
├── run/
├── temp/
│   └── asr/
└── model-cache/
```

Common overrides:

```bash
export CHATARCH_HOME=/srv/chatarch
# runtime root => /srv/chatarch/chatvoice

export CHATVOICE_HOME=/srv/chatvoice
# runtime root => /srv/chatvoice
```

The SQLite file can also be pointed directly:

```bash
export CHATVOICE_SQLITE_PATH=/srv/chatvoice/data/meetings.sqlite3
# or legacy-compatible:
export MEETING_DB_PATH=/srv/chatvoice/data/meetings.sqlite3
```

## Backend SQLite schema

Default database:

```text
~/.chatarch/chatvoice/data/meetings.sqlite3
```

Core tables:

| Table | Data | Notes |
| --- | --- | --- |
| `accounts` | invited accounts, display names, password salt/hash | no plaintext password |
| `auth_sessions` | login session hash, CSRF token, expiry | cookie stores only the session token |
| `api_tokens` | automation token id, hash, prefix, scopes, revoke/expiry metadata | raw token is returned once only |
| `meeting_records` | meeting title, timestamps, duration, transcript JSON, summary, preview | raw audio is not stored in DB |
| `conversation_records` | realtime conversation title, message JSON, preview | conversation audio is not stored |

Transcript segments, summaries, summary-edit chat messages, and realtime messages are stored as JSON strings in SQLite `TEXT` columns. List data endpoints return metadata / preview only; detail endpoints return transcript, summary, or messages.

## Browser-local data

Guest-mode data lives in the current browser's IndexedDB:

```text
IndexedDB: speakr-meetings
- guest meetings
- guest summaries and metadata
```

For signed-in accounts, meeting/conversation text is saved to server-side SQLite. The current meeting recorder does not provide recording archive/download controls and does not store recording chunks in browser IndexedDB. Audio is used only for realtime ASR; the durable result is text and summaries. See [Recording Storage Boundary](recording-storage.md).

## Temporary audio and model cache

- `temp/asr/`: temporary ASR upload, conversion, or worker files; jobs should clean this after processing.
- `model-cache/`: optional local model cache. The recommended production shape is `api-server`: keep GPU/model runtime behind a separate ASR API server and let the ChatVoice web process call it over HTTP.
- `logs/`: service logs should be collected/rotated by the supervisor/platform. Do not log raw audio, full transcripts, cookies, Authorization headers, or API keys.
- `run/`: PID/socket/runtime-control files.

## API key boundary

The Settings page shows only whether server-side API keys are configured. It never stores or submits raw key values in the browser. Production keys belong in server-side environment or protected config storage:

```bash
export CHATVOICE_ASR_CHANNEL=api-server
export CHATVOICE_ASR_API_URL="https://<asr-service>/v1/transcribe"
# Store CHATVOICE_ASR_API_KEY in the ChatEnv ChatVoice profile when the ASR endpoint requires it.
# Store OPENAI_API_BASE / OPENAI_API_KEY / OPENAI_API_MODEL in the ChatEnv ChatVoice profile.
# Production OPENAI_API_KEY should be a Token Plan sk-sp... key, not a usage-billed sk-... key.
```

## High-concurrency TODO

The `0.1.10` packaged legacy storage still supports SQLite WAL only. It is suitable for one service process, light concurrency, and controlled internal use:

```bash
chatvoice serve app --workers 1
```

High-concurrency production is tracked as TODO, not implemented in this release. Before scaling to multiple workers or nodes, migrate `accounts`, `auth_sessions`, `api_tokens`, `meeting_records`, and `conversation_records` to Postgres/MySQL and add a proper repository layer plus migration scripts.
