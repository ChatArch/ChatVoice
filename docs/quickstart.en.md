# Quick Start

The real HTTP recognition backend uses `CHATVOICE_ASR_API_URL`; see [configuration](configuration.md) for endpoint and credential setup.

Choose a goal first. A model-free trial checks the interface, not transcription or provider readiness.

<div class="grid cards" markdown>

- **Use an existing deployment**

    ---
    Open the Speakr URL supplied by its operator, then choose account or guest mode.

    [Web guide](web-guide.md)

- **Try the interface**

    ---
    Use `stub-local` without GPU models or cloud credentials.

    [UI trial](#ui-trial)

- **Run a real service**

    ---
    Configure real ASR and text models, then enable optional voice capabilities.

    [Real service](#real-service)

</div>

## Install {#install}

Python 3.10+ is required. This POSIX example uses a virtual environment under ChatArch home. Windows uses the same package with its platform-specific activation command.

```bash
python3 -m venv "$HOME/.chatarch/chatvoice/.venv"
. "$HOME/.chatarch/chatvoice/.venv/bin/activate"
python -m pip install "ChatVoice[web]==0.1.17"
chatvoice --version
chatvoice --tree
```

The `web` extra does not install CUDA, PyTorch or FunASR models.

## UI trial {#ui-trial}

```bash
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --dry-run --json
chatvoice serve app --host 127.0.0.1 --port 18087
```

Open `http://127.0.0.1:18087/` on the service machine and choose guest mode. Stop the foreground server with the terminal's normal interrupt.

!!! warning "Not real transcription"
    The stub channel loads no model. Summaries, Todo, TTS and realtime still require their own configured backends. A remote user's loopback address is not the server: use the deployment's HTTPS entry.

## Real service {#real-service}

| Capability | Required preparation |
| --- | --- |
| ASR | HTTP endpoint, or working local FunASR model and device in the service environment |
| Notes, revisions, Todo | Notes base URL, key and model |
| Automatic titles | Title base URL, key and model |
| System TTS | Protocol, endpoint, key, model, voices; resource ID for applicable protocols |
| Voice cloning | Reachable VoiceClone service; account and voice consent for generation |
| Realtime | Current Qwen realtime backend credentials and model entitlement |

Follow [configuration](configuration.md), then run:

```bash
chatenv test -t chatvoice -I
chatvoice serve app --host 127.0.0.1 --port 18087
```

The ChatEnv probe calls configured text/TTS backends and may consume quota. It does not fully validate ASR, realtime or voice cloning.

## Invite an account

Public registration is disabled. Set the password securely in `CHATVOICE_ACCOUNT_LOGIN` within the service environment, then run:

```bash
chatvoice accounts add member@example.com --display-name Member --password-env CHATVOICE_ACCOUNT_LOGIN --json
chatvoice accounts list --json
```

Never place the password in command arguments or public scripts. Sign in through the web app afterward. See [deployment](deployment.md) for persistent supervision and HTTPS.
