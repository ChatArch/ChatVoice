# ChatVoice Docs

ChatVoice is a ChatArch Python package that packages the Speakr recording, transcription, meeting-notes, and voice-workspace service into an installable and maintainable runtime.

Documentation entry: <https://arch.gh.wzhecnu.cn/ChatVoice/en/>

## Choose by scenario

| Scenario | Document |
| --- | --- |
| Install from PyPI and start the service | [Deployment and Startup](deployment.md) |
| Read back the real command tree and boundaries | [CLI Tree](cli-tree.md) |
| Check first-class capabilities and current boundaries | [Capability Map](capability-map.md) |
| Call package behavior directly from Python | [Python Interface Tree](interface-tree.md) |

## Core entries

<div class="grid cards" markdown>

- **Deployment and Startup**

    From `pip install "ChatVoice[web]==0.0.2"` to `chatvoice serve app`, including runtime paths, ASR API provider wiring, and database concurrency boundaries.

    [Read deployment guide](deployment.md)

- **CLI Tree**

    The real implemented command tree, command status, and update rules.

    [Read CLI tree](cli-tree.md)

- **Capability Map**

    Review current package boundaries and avoid presenting planned work as implemented functionality.

    [Read capability map](capability-map.md)

- **Python Interface Tree**

    Keep the CLI thin and put substantive behavior in importable Python APIs.

    [Read interface tree](interface-tree.md)

</div>

## v0.0.2 deployment boundary

- The packaged FastAPI app starts with `chatvoice serve app`.
- Production ASR should use `api-server` against a managed API or self-hosted GPU ASR server.
- `stub-local` is only for credential-free / GPU-free contract smoke.
- v0.0.2 defaults to SQLite WAL for one service process and light concurrency; high-concurrency storage migration needs a separate release.

## Preview docs locally

```bash
python -m pip install -e ".[docs]"
mkdocs serve
```

Chinese home is available at <https://arch.gh.wzhecnu.cn/ChatVoice/>.
