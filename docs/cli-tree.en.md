# CLI Tree

`chatvoice --tree` is the real command contract that must be read back whenever the CLI changes. The CLI parses arguments and renders output; actual behavior lives in importable Python functions.

See [Python Interface Tree](interface-tree.md) for API mapping. See [Deployment and Startup](deployment.md) for the packaged service flow.

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
└── service  # Plan and inspect ChatVoice service deployment
    └── plan [--host HOST] [--port PORT] [--workers WORKERS] [--ensure-dirs] [--json]  # Render a sanitized service deployment plan
```

## Base entries

```bash
chatvoice --help
chatvoice --version
chatvoice --tree
chatvoice paths --json
chatvoice doctor --json
```

## Start the service

```bash
python -m pip install "ChatVoice[web]==0.0.2"
chatvoice service plan --ensure-dirs --json
chatvoice serve app --host 127.0.0.1 --port 18087
```

For a self-hosted GPU ASR server or managed ASR API:

```bash
export CHATVOICE_ASR_CHANNEL=api-server
<ASR_API_URL_SETTING>="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.
chatvoice serve app --host 127.0.0.1 --port 18087
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
- Do not print tokens, cookies, Authorization headers, raw recordings, or full transcripts in CLI output or logs.
