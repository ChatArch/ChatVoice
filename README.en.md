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

ChatArch voice recording, transcription, and meeting-notes toolkit. ChatVoice packages the Speakr FastAPI + browser service so a release can be installed and started from the Python package.

Documentation entry: <https://arch.gh.wzhecnu.cn/ChatVoice/en/>

## Quick start from PyPI

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ChatVoice[web]==0.0.2"

chatvoice --tree
chatvoice service plan --ensure-dirs --json
chatvoice serve app --host 127.0.0.1 --port 18087
```

Open:

```text
http://127.0.0.1:18087/
```

## ASR provider model

Production ASR should run as an API provider. The provider can be a managed API or a self-hosted GPU ASR server:

```bash
export CHATVOICE_ASR_CHANNEL=api-server
<ASR_API_URL_SETTING>="https://<asr-service>/v1/transcribe"
# Configure the optional ASR bearer token in server-side config/env storage; do not put it in argv.
chatvoice serve app --host 127.0.0.1 --port 18087
```

For credential-free wiring smoke:

```bash
export CHATVOICE_ASR_CHANNEL=stub-local
chatvoice serve app --host 127.0.0.1 --port 18087
```

`funasr-gpu` and `funasr-cpu` remain compatibility channels, but the recommended production boundary is to keep GPU runtime behind an ASR API server and let ChatVoice call it over HTTP.

## Database and concurrency

v0.0.2 defaults to SQLite WAL under:

```text
<chatarch-home>/chatvoice/data/meetings.sqlite3
```

Use one service process with SQLite (`--workers 1`). High-concurrency production should migrate the storage layer to Postgres/MySQL before scaling workers or nodes. an external database URL setting is detected in `chatvoice doctor` / `chatvoice service plan`, but the v0.0.2 packaged legacy storage layer still supports SQLite only.

## CLI contract

```bash
chatvoice --tree
chatvoice paths --json
chatvoice doctor --json
chatvoice asr channels --json
chatvoice health status --url http://127.0.0.1:18087 --json
```

The CLI is a thin adapter over importable Python APIs. See `docs/interface-tree.md` for the function mapping.

## Documentation

Choose documentation by scenario:

| Scenario | Document |
| --- | --- |
| Install from PyPI and start the service | `docs/deployment.en.md` |
| Check implemented commands | `docs/cli-tree.en.md` |
| Check package capabilities and boundaries | `docs/capability-map.en.md` |
| Call package behavior directly from Python | `docs/interface-tree.md` |

## Development notes

See `DEVELOP.md` and `AGENTS.md` before expanding the package.
