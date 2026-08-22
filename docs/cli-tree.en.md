# CLI Tree

`chatvoice --tree` and `chatvoice --tree-brief` are rendered from the real Click registry by the shared `chatstyle.add_tree_option()`. The full tree keeps parameter signatures; the brief tree preserves the same nodes and purposes without signatures. The CLI parses arguments and renders output; actual behavior lives in importable Python functions.

See [Python Interface Tree](interface-tree.md) for API mapping, [Deployment and Startup](deployment.md) for the packaged service flow, and [API Access](api-access.md) for tokens and data export.

## Implemented commands

```text
chatvoice
├── --help  # Show this message and exit.
├── --version  # Show the version and exit.
├── --tree  # Print the registered CLI tree and exit.
├── --tree-brief  # Print the registered CLI tree without parameter signatures and exit.
├── accounts  # Manage invited accounts in the local service database.
│   ├── add <ACCOUNT> [--display-name DISPLAY-NAME] [--password-env PASSWORD-ENV] [--json]  # Create one invited account; writes the local service database.
│   └── list [--json]  # List invited account metadata; read-only, without passwords.
├── asr  # Inspect ASR provider configuration; no secret values.
│   └── channels [--json]  # List ASR channel readiness; read-only and secret-safe.
├── data  # Read meeting and conversation records from a running service.
│   ├── conversation <CONVERSATION-ID> [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # Read one realtime conversation; outputs stored messages.
│   ├── conversations [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # List realtime conversation metadata; read-only output.
│   ├── meeting <MEETING-ID> [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # Read one meeting; outputs its transcript and summary.
│   └── meetings [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # List meeting metadata; read-only text or JSON output.
├── doctor [--json]  # Check local service readiness; read-only and secret-safe.
├── health  # Read health from a running ChatVoice service; no writes.
│   └── status [--url URL] [--timeout TIMEOUT] [--json]  # Read /api/status; returns redacted text or JSON.
├── paths [--json]  # Show resolved runtime paths; read-only text or JSON output.
├── serve  # Start packaged ChatVoice services; long-running side effects.
│   └── app [--host HOST] [--port PORT] [--reload] [--workers WORKERS] [--dry-run] [--json]  # Start the Speakr web app; --dry-run only prints a safe plan.
├── service  # Plan and inspect ChatVoice service deployment.
│   └── plan [--host HOST] [--port PORT] [--workers WORKERS] [--ensure-dirs] [--json]  # Render a safe plan; --ensure-dirs creates runtime directories.
└── tokens  # Manage service API tokens; remote credential side effects.
    ├── create [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--name NAME] [--expires-days EXPIRES-DAYS] [--scope SCOPES] [--timeout TIMEOUT] [--json]  # Create a remote token; prints its secret value exactly once.
    ├── list [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # List remote token metadata; read-only, without token values.
    └── revoke <TOKEN-ID> [--url URL] [--account ACCOUNT] [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # Revoke a remote API token by id; destructive credential write.
```

## Brief command tree

```text
chatvoice
├── --help  # Show this message and exit.
├── --version  # Show the version and exit.
├── --tree  # Print the registered CLI tree and exit.
├── --tree-brief  # Print the registered CLI tree without parameter signatures and exit.
├── accounts  # Manage invited accounts in the local service database.
│   ├── add  # Create one invited account; writes the local service database.
│   └── list  # List invited account metadata; read-only, without passwords.
├── asr  # Inspect ASR provider configuration; no secret values.
│   └── channels  # List ASR channel readiness; read-only and secret-safe.
├── data  # Read meeting and conversation records from a running service.
│   ├── conversation  # Read one realtime conversation; outputs stored messages.
│   ├── conversations  # List realtime conversation metadata; read-only output.
│   ├── meeting  # Read one meeting; outputs its transcript and summary.
│   └── meetings  # List meeting metadata; read-only text or JSON output.
├── doctor  # Check local service readiness; read-only and secret-safe.
├── health  # Read health from a running ChatVoice service; no writes.
│   └── status  # Read /api/status; returns redacted text or JSON.
├── paths  # Show resolved runtime paths; read-only text or JSON output.
├── serve  # Start packaged ChatVoice services; long-running side effects.
│   └── app  # Start the Speakr web app; --dry-run only prints a safe plan.
├── service  # Plan and inspect ChatVoice service deployment.
│   └── plan  # Render a safe plan; --ensure-dirs creates runtime directories.
└── tokens  # Manage service API tokens; remote credential side effects.
    ├── create  # Create a remote token; prints its secret value exactly once.
    ├── list  # List remote token metadata; read-only, without token values.
    └── revoke  # Revoke a remote API token by id; destructive credential write.
```

## Fresh-start service entry

```bash
python -m pip install "ChatVoice[web]==0.1.10"
chatvoice service plan --ensure-dirs --json
chatvoice serve app --host 127.0.0.1 --port 18087
```

## Accounts, tokens, and data reads

```bash
read -r -s CHATVOICE_ACCOUNT_LOGIN
export CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts add person@example.com --display-name "Person" --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice tokens create --url http://127.0.0.1:18087 --account person@example.com --password-env CHATVOICE_ACCOUNT_LOGIN --name automation --json

read -r -s CHATVOICE_DATA_READ
export CHATVOICE_DATA_READ
chatvoice data meetings --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
chatvoice data conversations --url http://127.0.0.1:18087 --token-env CHATVOICE_DATA_READ --json
```

## Status contract

| Status | Meaning |
| --- | --- |
| Implemented | Command, Python function, and tests exist |
| Verified | Local tests, builds, or release smoke have passed |
| Planned / checkpoint | Boundary notes only; not a user tutorial yet |

## Update checklist

- Every substantive CLI command maps to a Python function, class, or service layer.
- Update README, CLI tree, interface tree, capability map, tests, and deployment docs together.
- Remote-state or service-restart commands need dry-run / plan / readback boundaries first.
- Do not print tokens, cookies, Authorization headers, raw recordings, or full transcripts in diagnostics, logs, or PR notes; data export commands return record contents only when explicitly invoked.
