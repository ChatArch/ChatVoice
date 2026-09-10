# Python Interface Tree

The CLI is a thin adapter over these Python capabilities. Local storage, server processing and remote data access remain separate. Consult the installed package for complete signatures.

| Goal | Modules |
| --- | --- |
| Local accounts, paths and backup | `accounts`, `paths`, `backup` |
| Start or inspect services | `service`, `health`, `doctor`, `web.server` |
| Call a running service | `client.ChatVoiceClient` and convenience functions |
| Embed model adapters or Todo conversion | `text_api`, `tts_api`, `todo_markdown` |

## Paths, accounts and backup

```text
chatvoice
├── paths
│   ├── RuntimePaths / state_paths() / state_root()  # Resolve runtime paths
│   ├── ensure_runtime_dirs()                      # Create directories
│   └── database_settings()                        # Sanitized storage state
├── accounts
│   ├── create_account(account, password, display_name=None)
│   └── list_accounts()
└── backup
    ├── dump_database(output, *, overwrite=False)
    └── import_database(input_path, *, backup_current=True)
```

```python
from chatvoice.paths import state_paths
from chatvoice.backup import dump_database

paths = state_paths()
result = dump_database(paths.root / "backup.sqlite3")
```

This example writes a backup. Stop the service before importing one. See [runtime layout](runtime-layout.md).

## Service entry points

```text
chatvoice
├── service.render_service_plan(*, host, port, workers)  # Read-only plan
├── service.serve_app(*, host, port, reload, workers)     # Start service
├── web.server.create_app()                             # FastAPI factory
├── health.get_status(base_url, *, timeout)              # HTTP status
├── doctor.run_doctor()                                 # Local inspection
└── asr.get_asr_channels()                              # ASR configuration map
```

The application factory uses package configuration and runtime paths; it is not an isolated sandbox. Set the intended environment before embedding it.

## Remote client

```text
chatvoice.client
├── ChatVoiceClient(base_url, timeout)
│   ├── login(account, password)
│   ├── create_token(...) / list_tokens() / revoke_token(token_id)
│   ├── list_meetings(token) / get_meeting(token, meeting_id)
│   └── list_conversations(token) / get_conversation(token, conversation_id)
├── create_remote_token(...) / list_remote_tokens(...) / revoke_remote_token(...)
├── list_remote_meetings(base_url, token) / get_remote_meeting(base_url, token, meeting_id)
└── list_remote_conversations(base_url, token) / get_remote_conversation(base_url, token, conversation_id)
```

```python
import os
from chatvoice.client import get_remote_meeting

meeting = get_remote_meeting(
    "https://speakr.example.com",
    os.environ["CHATVOICE_DATA_READ"],
    "MEETING_ID",
)
print(meeting.get("todo_markdown", ""))
```

The token needs the matching scope. `ChatVoiceApiError` exposes `status_code`; avoid publishing private records in error logs.

## Model and Todo modules

```text
chatvoice
├── config.ChatVoiceConfig                           # Typed ChatEnv registration
├── text_api
│   ├── resolve_text_settings(values, purpose, *, req_model=None)
│   ├── complete_text(settings, messages, ...)
│   └── stream_text(settings, messages, ...)
├── tts_api
│   ├── resolve_tts_settings(values)
│   └── synthesize(settings, text, *, voice=None, format='mp3')
└── todo_markdown
    ├── generate_todo(summary, call_model)
    └── revise_todo(summary, current_todo, instruction, messages, call_model)
```

Todo functions do not persist data. The injected `call_model` accepts keyword arguments `transcript` and `instruction`, returning a dict with `content` and `model`. The module validates shape and bounds, not semantic truth. Most integrations should use the deployed [Todo HTTP endpoints](api-access.md#todo) rather than private web-module helpers.

## CLI mapping

| CLI | Python |
| --- | --- |
| `paths` / `doctor` | `state_paths` / `run_doctor` |
| `serve app` / `service plan` | `serve_app` / `render_service_plan` |
| `accounts add/list` | `create_account` / `list_accounts` |
| `tokens create/list/revoke` | Corresponding remote-token client functions |
| `data meeting(s)/conversation(s)` | Corresponding `get_remote_*` / `list_remote_*` functions |
| `data dump/import` | `dump_database` / `import_database` |

[Full CLI tree](cli-tree.md) · [Capability boundaries](capability-map.md)
