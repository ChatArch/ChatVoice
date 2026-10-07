# ChatVoice

[Documentation](https://arch.gh.wzhecnu.cn/ChatVoice/en/) · [Chinese README](README.md) · [PyPI](https://pypi.org/project/ChatVoice/) · [Source](https://github.com/ChatArch/ChatVoice) · [Runtime and backup](https://arch.gh.wzhecnu.cn/ChatVoice/en/runtime-layout/)

ChatVoice is the ChatArch Python package behind the Speakr recording and meeting workspace. Turn speech into text, refine a summary, and explicitly convert useful ideas into an editable Markdown Todo.

## Choose your task

| Goal | Start here |
| --- | --- |
| Install and open the app | [Quick start](https://arch.gh.wzhecnu.cn/ChatVoice/en/quickstart/) |
| Record, summarize and refine notes | [Web guide](https://arch.gh.wzhecnu.cn/ChatVoice/en/web-guide/) |
| Convert a summary into an action plan | [Markdown Todo](https://arch.gh.wzhecnu.cn/ChatVoice/en/markdown-todo/) |
| Configure ASR, text, TTS or voice cloning | [Configuration](https://arch.gh.wzhecnu.cn/ChatVoice/en/configuration/) |
| Deploy, invite accounts and back up data | [Deployment](https://arch.gh.wzhecnu.cn/ChatVoice/en/deployment/) |
| Integrate with automation | [CLI tree](https://arch.gh.wzhecnu.cn/ChatVoice/en/cli-tree/) · [HTTP API](https://arch.gh.wzhecnu.cn/ChatVoice/en/api-access/) · [Python interfaces](https://arch.gh.wzhecnu.cn/ChatVoice/en/interface-tree/) |

## Install and inspect

Python 3.10+ is required. Use a dedicated virtual environment.

```bash
python -m pip install "ChatVoice[web]==0.3.2"
chatvoice --version
chatvoice --tree
chatvoice serve app --dry-run --json
```

Installation neither starts a service nor downloads GPU models. The quick start separates a model-free UI trial from real transcription.

## Capabilities

- Meeting recording, live transcription, pause/resume, titles, tags and history. Audio is discarded by default; account users may explicitly retain recordings for owner-protected playback and download.
- A blank meeting has exactly two routes: recognition-only discards source audio with no replay; signed-in users may choose recording + recognition to retain and replay this meeting. First start locks the route permanently. Import requires login, always retains the source for replay, and supports files up to 128 MiB (over 12 MiB uses sequential 30-second ASR windows).
- Summary generation, direct editing, conversation-based refinement and undo.
- Explicit summary-to-Todo conversion, a separate Markdown editor and refinement conversation, copy and `.md` export. No automatic conversion or task execution.
- Configurable system TTS and an independent one-shot voice-cloning service.
- Qwen realtime voice conversations when the configured backend grants access.
- CLI and Python clients, scoped API tokens and single-file SQLite backup/restore.

Model configuration is server-side. Independent text settings serve notes and titles; Todo reuses the notes model. HTTP ASR uses `CHATVOICE_ASR_API_URL`, while local FunASR requires additional model/runtime dependencies.

## Data and security

Account records use SQLite below `~/.chatarch/chatvoice`. Guest records remain in the browser. Original audio is discarded by default; explicit account opt-in stores private files associated with the meeting. Playback, download and deletion check ownership. Guests cannot retain server recordings. Provider keys never reach the browser.

Clearing does not unlock a meeting route; a finished meeting needs a new meeting for more audio. Explicit clear/delete keeps existing cleanup semantics, while migration never deletes legacy audio. A database backup does not include recording bytes; back up the private audio directory together with the database when retention is used.

Self-registration is disabled; operators provision invited accounts. ChatVoice uses the built-in `ChatVoiceAuth` backend from ChatLogin 0.1.2 and a customizable shared `LoginUI` at `/login`. Existing accounts, sessions and CSRF remain compatible; ChatVoice retains owner and token policy. Guest drafts must commit their IndexedDB transaction before login navigation.

## Development

```bash
python -m pip install -e ".[web,dev,docs]"
python -m pytest tests -q
mkdocs build --strict
```

Frontend controller tests require Node.js 22+. Offline tests are not evidence of live model availability; see [testing](https://arch.gh.wzhecnu.cn/ChatVoice/en/testing/).
