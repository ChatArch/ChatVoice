# Deployment and Startup

Choose a service shape first. ChatVoice ships a web server, not a system-service installer or reverse-proxy manager.

| Shape | Use | Requirement |
| --- | --- | --- |
| Foreground single process | Development and controlled trials | Stops when the terminal exits |
| User-level systemd | Persistent Linux service | Durable virtual environment, data root and graceful shutdown |
| Separate ASR HTTP service | Separate GPU and web runtime | Real endpoint in `CHATVOICE_ASR_API_URL` |
| In-process FunASR | Prepared local model environment | Compatible CUDA/PyTorch, prewarm, no per-request reload |

## Install and inspect

```bash
python -m pip install "ChatVoice[web]==0.1.17"
chatvoice paths --json
chatvoice doctor --json
chatvoice service plan --ensure-dirs --json
chatvoice serve app --dry-run --json
```

Code lives in Python `site-packages`; state defaults to `~/.chatarch/chatvoice`. Use the [configuration reference](configuration.md) for server-side model credentials. Summary and title models are independent; Todo reuses the notes model.

When overriding paths, give the same process environment to local account commands and the web service:

```bash
export CHATARCH_HOME="$HOME/.chatarch"
export CHATVOICE_HOME="$CHATARCH_HOME/chatvoice"
export CHATVOICE_SQLITE_PATH="$CHATVOICE_HOME/data/meetings.sqlite3"
```

## Provision an account

Supply `CHATVOICE_ACCOUNT_LOGIN` securely before running:

```bash
chatvoice accounts add member@example.com --display-name Member --password-env CHATVOICE_ACCOUNT_LOGIN
chatvoice accounts list --json
```

Self-registration is disabled. The ChatLogin host adapter reuses existing account IDs, password material and sessions without creating a replacement user database.

## Foreground server

```bash
chatvoice serve app --host 127.0.0.1 --port 18087 --workers 1
```

Loopback is for same-machine validation. Remote users need the deployed HTTPS entry. Forward WebSockets and avoid buffering revision SSE at the proxy; provider credentials remain server-side.

## User-level systemd example

Ensure the virtual environment and data root exist. Save this thin unit as `~/.config/systemd/user/chatvoice.service`. The `service plan` command does not install it.

```ini
[Unit]
Description=ChatVoice Speakr
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/.chatarch/chatvoice
Environment=CHATVOICE_HOME=%h/.chatarch/chatvoice
ExecStart=%h/.chatarch/chatvoice/.venv/bin/chatvoice serve app --host 127.0.0.1 --port 18087 --workers 1
Restart=on-failure
KillSignal=SIGINT
SendSIGKILL=no
TimeoutStopSec=120

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now chatvoice.service
systemctl --user status chatvoice.service
journalctl --user -u chatvoice.service -n 100 --no-pager
```

Check host policy for user-service lifetime after logout. Proxy settings, `ffmpeg` and model dependencies must be available in the actual service environment; an interactive shell does not establish systemd readiness.

## Validate and upgrade

1. Read version, `database.ok` and ASR state from `/api/heartbeat`.
2. Use short synthetic content to test enabled ASR, summary, title, Todo and TTS paths independently.
3. Verify account/guest storage, refresh and the real user-facing URL, not only loopback.
4. Preserve the previous package, configuration and a consistent database backup. Pin the upgrade and avoid unrelated GPU dependency changes.
5. Stop/start through the supervisor, then verify the new process, version, dependency diff and real operations.

Do not restore an old database over new user records merely to roll back code. See [backup/restore](runtime-layout.md#backup) and [troubleshooting](troubleshooting.md).
