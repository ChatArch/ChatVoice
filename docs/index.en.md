# ChatVoice Documentation

Move from speech to a clear next step. ChatVoice provides the Speakr web app, CLI and Python interfaces. Choose a task rather than reading a linear setup diary.

<div class="grid cards" markdown>

- :material-rocket-launch: **Run the service**

    ---
    Install, try the UI without a model, and choose real transcription.

    [Quick start](quickstart.md)

- :material-microphone: **Record and refine notes**

    ---
    Recording, pause/resume, summaries, manual edits and conversation refinement.

    [Web guide](web-guide.md)

- :material-checkbox-marked-outline: **Turn ideas into Todo**

    ---
    Explicit conversion, continued refinement and ordinary Markdown export.

    [Markdown Todo](markdown-todo.md)

- :material-cog: **Configure and deploy**

    ---
    Separate ASR, text, TTS, realtime and voice-cloning requirements.

    [Configuration](configuration.md) · [Deployment](deployment.md)

- :material-console: **Integrate applications**

    ---
    Inspect real commands, HTTP contracts and importable Python functions.

    [CLI tree](cli-tree.md) · [HTTP API](api-access.md) · [Python interfaces](interface-tree.md)

- :material-shield-check: **Understand boundaries**

    ---
    Retention, authorization, failure handling and verification.

    [Data retention](recording-storage.md) · [Troubleshooting](troubleshooting.md) · [Testing](testing.md)

</div>

## Choose by role

| Role | Suggested path |
| --- | --- |
| Web user | Web guide, then Todo or voice cloning |
| Operator | Quick start, configuration, deployment, troubleshooting |
| Integrator | Capability map, CLI tree, HTTP/Python reference |
| Contributor | Python interfaces, testing |

## Core boundaries

- Account records live on the server; guest records live in the current browser.
- Meeting audio is not retained as a recording archive. Text, summaries and Todo can be saved.
- Todo conversion is explicit and never executes tasks automatically.
- Installation, configured fields, model discovery and successful live operations are separate states.

[Capability map](capability-map.md)
