# CLI Tree

`chatstyle.add_tree_option()` derives `--tree` and `--tree-brief` from registered commands.

This topology comes from the real `chatvoice --tree`. Read it by responsibility; signatures are preserved and comments describe effects.

## Top-level entries

```text
chatvoice
├── --help  # Show this message and exit.
├── --version  # Show the version and exit.
├── --tree  # Print the registered CLI tree and exit.
├── --tree-brief  # Print the registered CLI tree without parameter signatures and exit.
├── accounts  # Manage invited accounts in the local service database.
├── asr  # Inspect ASR provider configuration; no secret values.
├── data  # Read meeting and conversation records from a running service.
├── doctor [--json]  # Check local service readiness; read-only and secret-safe.
├── health  # Read health from a running ChatVoice service; no writes.
├── paths [--json]  # Show resolved runtime paths; read-only text or JSON output.
├── serve  # Start packaged ChatVoice services; long-running side effects.
├── service  # Plan and inspect ChatVoice service deployment.
└── tokens  # Manage service API tokens; remote credential side effects.
```

## `accounts`

```text
chatvoice accounts
├── add <ACCOUNT> [--display-name DISPLAY-NAME] [--password-env PASSWORD-ENV] [--json]  # Create one invited account; writes the local service database.
└── list [--json]  # List invited account metadata; read-only, without passwords.
```

Account commands modify the local service database, not a remote account API. Passwords come from the variable named by `--password-env`.

## `asr`

```text
chatvoice asr
└── channels [--json]  # List ASR channel readiness; read-only and secret-safe.
```

These commands inspect configuration. They do not run a model or establish transcription quality; use the web or ASR endpoints for actual recognition.

## `data`

```text
chatvoice data
├── conversation <CONVERSATION-ID> [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # Read one realtime conversation; outputs stored messages.
├── conversations [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # List realtime conversation metadata; read-only output.
├── dump [--output OUTPUT-PATH] [--overwrite] [--json]  # Dump local ChatVoice data to one consistent SQLite file.
├── import <INPUT-PATH> [--yes] [--no-backup-current] [--json]  # Import one SQLite dump as the active local database; stop the service first.
├── meeting <MEETING-ID> [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # Read one meeting; outputs its transcript and summary.
└── meetings [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # List meeting metadata; read-only text or JSON output.
```

Meeting/conversation reads use `--url` and a Bearer token named by `--token-env`. Dump/import operate on local SQLite. Stop the service before import; a current-database backup is made by default.

## `health`

```text
chatvoice health
└── status [--url URL] [--timeout TIMEOUT] [--json]  # Read /api/status; returns redacted text or JSON.
```

Health status reads `/api/status`; connectivity does not establish every model entitlement or sidecar availability.

## `serve`

```text
chatvoice serve
└── app [--host HOST] [--port PORT] [--reload] [--workers WORKERS] [--dry-run] [--json]  # Start the Speakr web app; --dry-run only prints a safe plan.
```

Keep one service process with SQLite. Reload is for development; dry-run opens no listening port.

## `service`

```text
chatvoice service
└── plan [--host HOST] [--port PORT] [--workers WORKERS] [--ensure-dirs] [--json]  # Render a safe plan; --ensure-dirs creates runtime directories.
```

Service plan neither installs systemd units nor restarts a service. Only explicit `--ensure-dirs` creates runtime directories.

## `tokens`

```text
chatvoice tokens
├── create [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--name NAME] [--expires-days EXPIRES-DAYS] [--scope SCOPES] [--timeout TIMEOUT] [--json]  # Create a remote token; prints its secret value exactly once.
├── list [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # List remote token metadata; read-only, without token values.
└── revoke <TOKEN-ID> [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # Revoke a remote API token by id; destructive credential write.
```

These commands log into a remote service. Token creation returns a one-time secret; keep it out of public logs. Revocation invalidates that token.

## Common paths

| Goal | Command or entry |
| --- | --- |
| Resolve paths | `chatvoice paths --json` |
| Inspect the local environment | `chatvoice doctor --json` |
| Preview startup | `chatvoice serve app --dry-run --json` |
| Work with Todo | Web, HTTP or Python; there is no Todo CLI subtree |

ChatVoice primarily uses explicit arguments. ChatEnv interactive flags `-i` / `-I` belong to that configuration tool, not unsupported ChatVoice commands.

[HTTP API](api-access.md) · [Python interfaces](interface-tree.md) · [Configuration](configuration.md)
