# CLI Tree

`chatvoice --tree` is the real command contract that must be read back whenever the CLI changes. The CLI parses arguments and renders output; actual behavior lives in importable Python functions.

See [Python Interface Tree](interface-tree.md) for API mapping, [Deployment and Startup](deployment.md) for the packaged service flow, and [API Access](api-access.md) for tokens and data export.

## Implemented commands

```text
chatvoice  # ChatVoice command line interface
├── --help  # Show help for the current command.
├── --version  # Show package version.
├── --tree  # Print the registered CLI tree.
├── paths [--json]  # Show resolved ChatVoice runtime paths
├── doctor [--json]  # Check local ChatVoice service readiness without secrets
├── serve  # Start packaged ChatVoice services
│   └── app [--host HOST] [--port PORT] [--reload] [--workers WORKERS] [--dry-run] [--json]  # Start the packaged Speakr web application
├── health  # Read health from a running ChatVoice service
│   └── status [--url URL] [--timeout TIMEOUT] [--json]  # Read the /api/status endpoint
├── asr  # Inspect ASR provider configuration
│   └── channels [--json]  # List ASR channels and API-provider readiness
├── accounts  # Manage invited accounts in the local service database
│   ├── add ACCOUNT [--display-name DISPLAY-NAME] [--password-env PASSWORD-ENV] [--json]  # Create one invited account from the packaged runtime
│   └── list [--json]  # List invited account metadata without password material
├── tokens  # Manage service API tokens for automation
│   ├── create [--url URL] --account ACCOUNT [--password-env PASSWORD-ENV] [--name NAME] [--expires-days EXPIRES-DAYS] [--scope SCOPES] [--timeout TIMEOUT] [--json]  # Create a one-time-visible API token after account login
│   ├── list [--url URL] --account ACCOUNT [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # List API token metadata without revealing token values
│   └── revoke TOKEN-ID [--url URL] --account ACCOUNT [--password-env PASSWORD-ENV] [--timeout TIMEOUT] [--json]  # Revoke an API token by id
├── data  # Read meeting and conversation data from a running service
│   ├── meetings [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # List meeting metadata; use data meeting for transcript and summary
│   ├── meeting MEETING-ID [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # Read one meeting with transcript and summary
│   ├── conversations [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # List realtime conversation metadata; use data conversation for messages
│   └── conversation CONVERSATION-ID [--url URL] [--token-env TOKEN-ENV] [--timeout TIMEOUT] [--json]  # Read one realtime conversation with messages
└── service  # Plan and inspect ChatVoice service deployment
    └── plan [--host HOST] [--port PORT] [--workers WORKERS] [--ensure-dirs] [--json]  # Render a sanitized service deployment plan
```

## Fresh-start service entry

```bash
python -m pip install "ChatVoice[web]==0.1.1"
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
