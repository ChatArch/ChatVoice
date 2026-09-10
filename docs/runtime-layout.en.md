# Runtime Layout and Data Structure

Keep installed code, persistent state and temporary processing files separate.

| Data | Location |
| --- | --- |
| Package code | Current environment's `site-packages/chatvoice` |
| Configuration | ChatEnv `envs/ChatVoice/` |
| Account records | One SQLite file |
| Guest records | Current-browser IndexedDB |
| ASR intermediates | Runtime `temp/asr` |
| Model cache | Runtime `model-cache` or explicitly selected model cache |

## Default layout

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

```bash
chatvoice paths --json
chatvoice doctor --json
```

Root precedence is explicit Python `chatvoice_home`, process `CHATVOICE_RUNTIME_ROOT` (compatibility), `CHATVOICE_HOME`, `CHATARCH_HOME/chatvoice`, then `~/.chatarch/chatvoice`. Database overrides are process `MEETING_DB_PATH` (compatibility) and `CHATVOICE_SQLITE_PATH`.

Typed ChatEnv registration does not export values into arbitrary CLI processes. Give account commands, backup commands and the service launcher the same path environment.

## SQLite schema {#schema}

| Table | Content |
| --- | --- |
| `accounts` | Account metadata and password-verification material |
| `auth_sessions` | Session digests, CSRF and expiry |
| `api_tokens` | Token digests, scopes, expiry and revocation |
| `meeting_records` | Transcript, tags, summary/refinement history, Markdown Todo and Todo history |
| `conversation_records` | Realtime conversation text and model/voice metadata |

Transcript segments, tags and messages use JSON text columns; summaries and `todo_markdown` are document text. Raw recordings are not database fields. Old records have empty Todo content; clients omitting Todo fields do not clear stored values.

Storage is single-node SQLite WAL. There is no implemented Postgres/MySQL switch; adding web workers is not a database migration.

## Consistent backup and restore {#backup}

```bash
chatvoice data dump --output "$HOME/.chatarch/chatvoice/backup.sqlite3" --json
```

The command uses a consistent SQLite snapshot. Copying only the main database file during active writes can miss WAL state.

Restore replaces the active database. Stop the service first and verify the input:

```bash
systemctl --user stop chatvoice.service
chatvoice data import "$HOME/.chatarch/chatvoice/backup.sqlite3" --yes --json
systemctl --user start chatvoice.service
```

Current data is backed up by default; `--no-backup-current` disables that protection. Database restore is not a routine code-upgrade step and must not overwrite newer records.

## Temporary files and logs

ASR may create temporary files for decoding/recognition and cleans them during normal processing. Inspect owned leftovers after abnormal termination. Temporary synthesized audio and raw meeting recordings have different retention boundaries; see [data retention](recording-storage.md).

A `logs/` directory does not mean every request is automatically written to a fixed log file. For a systemd deployment, inspect the unit journal; logging destinations depend on the launcher.
