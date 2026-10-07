# Capability Map

This map explains what ChatVoice owns. Invocation details live in the [CLI tree](cli-tree.md), [HTTP API](api-access.md) and [Python interface tree](interface-tree.md).

| Capability | Entry | Dependency/boundary |
| --- | --- | --- |
| Recording and transcription | Web, ASR HTTP/WebSocket | Microphone permission and configured ASR; stub is only a fixture |
| Two meeting routes and lock | Web and meeting-audio APIs | Choose recognition-only or recording + recognition while blank; first start persists the lock and finished meetings reject append |
| Existing audio import | Web and meeting-import APIs | Login required, always retained and replayable; configured ASR, 128 MiB, cancellation/rollback |
| Summaries and refinement | Web, notes API | Independent text model; transcript is retained |
| Markdown Todo | Web, Todo API, Python callback module | Explicit conversion/edit/refinement/undo/export; no task execution |
| Meeting and conversation storage | Web and account APIs | Account SQLite or guest IndexedDB |
| Read-only data integration | Token, CLI, Python | Scopes and ownership |
| System speech synthesis | Voice studio, TTS API | Independent TTS settings and dynamic voices |
| One-shot cloning | Voice studio, clone proxy | Account, authorized reference and independent sidecar |
| Realtime voice conversation | Web and WebSocket | Realtime entitlement is separate from TTS entitlement |
| Diagnostics and backup | CLI, Python | Local paths and single-file SQLite |

## Interpret evidence correctly

| Evidence | Establishes | Does not establish |
| --- | --- | --- |
| Registered `--tree` command | An implemented invocation surface | External-service configuration |
| Offline regression | Tested business contracts | Microphone/network/model quota |
| Healthy status endpoint | Readable state at that time | Correct generated audio |
| Real generation/save/readback | The exercised path's result | Every provider and scenario |

## Outside current scope

- Todo execution, mind maps or cross-system task orchestration.
- A general recording-file library, raw realtime-conversation archives, permanent cloned-voice libraries or generated-audio history.
- Postgres/MySQL switching or distributed storage.
- Automatic deployment/migration of every model backend or proxy management.

[Quick start](quickstart.md) · [Web guide](web-guide.md) · [Configuration](configuration.md)
