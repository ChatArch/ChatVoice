# Changelog

## 0.1.9 - 2026-08-22

### Added

- Voice Studio is now one unified `生成声音` panel: system voices (龙安灵心 / 龙安鲁风) and **我的复刻声音** are selectable voice cards in the same list, sharing one text box.
- Local one-shot voice cloning via the VoiceClone sidecar: upload or record an authorized reference audio sample, enter new text, and generate a temporary preview audio with progress, playback, and download.
- The cloned voice is reusable within the session: switching between system voices and the cloned voice keeps the reference audio, and new text can be generated repeatedly without re-uploading.
- The studio text box now ships with a pre-filled default example so the flow can be tested without typing first.
- New authenticated APIs: `GET /api/voice-clone/status`, `POST /api/voice-clone/jobs`, `GET /api/voice-clone/jobs/{id}`, `GET /api/voice-clone/jobs/{id}/audio`, `DELETE /api/voice-clone/jobs/{id}`.
- New user guide: `docs/voice-cloning.md` / `docs/voice-cloning.en.md`.

### Changed

- System TTS without a model key now shows a clear `未配置模型 Key` disabled state and `/api/tts` returns `503` instead of `500`.
- Removed the separate "文字与声音" composer and the separate "本地复刻 · 一次性生成" card; legacy custom voice-id enrollment UI is removed from Voice Studio.
- `chatvoice.cli` keeps working with older public ChatStyle wheels via a fallback `add_tree_option`.

## 0.1.8 - 2026-08-22

### Changed

- Replace the package-local Click tree renderer with ChatStyle `add_tree_option()`, explicitly name the `chatvoice` root, and add `--tree-brief` alongside the existing `--version` and full `--tree` contract.
- Align the runtime with `chatstyle>=0.2.0,<0.3.0`, `chatenv>=0.2.10,<0.3.0`, bounded Click/docs dependencies, typed ChatEnv provider storage checks, and installed/built-wheel CLI release gates.

## 0.1.7 - 2026-08-22

### Changed

- Move recorder copy actions into their content areas: transcript copy stays in the transcript panel, summary copy stays in the summary panel, and the global top-right copy action is removed.
- Replace the top-right toolbar action with a compact vertical `•••` menu containing only Settings, Docs, and GitHub; keep the three top-level workspace tabs visible for page switching.
- Rework API Token creation around a one-time-visible token result: generation attempts clipboard copy, the manual copy button remains available before closing, delete wording replaces revoke wording, revoked/deleted tokens are hidden, and expiry choices are limited to 7/15/30/90 days or permanent.
- Make meeting title actions icon-only (`↻` and `＋`) with hover/focus tooltips, keeping the mobile title row compact.
- Remove the meeting recorder's browser-local raw-audio archive/download control. The current recorder now presents one clear boundary: audio is used for realtime transcription only, while durable storage is text, summaries, and metadata.
- Add MkDocs recording-storage boundary docs explaining that pure recording/file-library support should be designed as a separate future capability.

## 0.1.6 - 2026-08-20

### Changed

- Make the recorder audio-retention/privacy notice more prominent in the recording console so users do not miss that original audio is not saved by default.

## 0.1.5 - 2026-08-20

### Changed

- Clarify the recorder homepage toolbar: move the history/sidebar menu to the left, remove the inactive language button, and replace ambiguous icon-only controls with labeled `设置/状态` and `复制` actions.
- Make recorder header actions more visible with stronger `刷新标题` and `新建` affordances.
- Change raw audio retention to explicit opt-in. By default, ChatVoice does not save original recordings in the browser or on the server; users can click `保存音频` to keep local browser chunks for download after the recording ends.
- Clarify privacy copy across entry, sidebar, and recorder console: logged-in accounts sync text, summaries, and metadata, while original audio is not uploaded or saved by default.

## 0.1.4 - 2026-08-19

### Added

- Add a direct **新建** button in the recorder header for faster mobile topic creation.
- Add a **刷新标题** button that regenerates the meeting title from the current full transcript and summary context.
- Add a confirmation guard before clearing/resetting a meeting with existing content.

### Changed

- Pausing a recording now commits the current ASR window so pending rewrite/live text can be finalized while paused.
- Automatic title refresh can update AI-generated titles from later full-session content, while manual titles remain protected unless the user explicitly clicks refresh.

## 0.1.3 - 2026-08-19

### Added

- Add `GET /api/heartbeat` with lightweight service/database/ASR health, model warm-up, and recent ASR success/failure metadata.
- Add Web Settings ASR heartbeat display so operators can see whether recognition is ready, processing, or degraded.
- Emit `asr.stream.processing` and periodic `asr.stream.heartbeat` WebSocket events while realtime recognition is running.

### Fixed

- Avoid silent recorder behavior during FunASR GPU cold start or long ASR chunks by surfacing model-loading, processing, and failure messages in the browser.

## 0.1.2 - 2026-08-18

### Added

- Add a server-side API key status panel in web settings. The browser can see whether ASR, summary/realtime model, and voice-cloning keys are configured, but it never stores or submits raw key values.
- Document the installed code location, default runtime root, `~/.chatarch/chatvoice` directory layout, SQLite tables, browser IndexedDB boundary, `temp/asr`, `model-cache`, and the high-concurrency Postgres/MySQL TODO.
- Add runtime layout docs to MkDocs navigation.

### Fixed

- Expose sanitized `/api/status` fields for API-key readiness and ASR endpoint host without leaking key values.

## 0.1.1 - 2026-08-18

### Fixed

- Reject explicit empty API-token scope lists instead of silently granting the default read scopes; omitted `scopes` still receives the default `read:meetings` and `read:conversations` scopes.
- Keep list data endpoints metadata-only; meeting/conversation detail endpoints return transcripts, summaries, and messages.
- Clear one-time token values from the web settings DOM on unauthenticated render, mode switch, dialog close/cancel, and logout.
- Align `chatvoice.paths`, `chatvoice accounts`, and the packaged web app on `CHATVOICE_RUNTIME_ROOT`, `CHATVOICE_HOME`, `CHATARCH_HOME`, `MEETING_DB_PATH`, and `CHATVOICE_SQLITE_PATH` resolution.
- Update public install/docs examples to `ChatVoice[web]==0.1.1` and replace ASR URL placeholders with executable `CHATVOICE_ASR_API_URL` setup.

## 0.1.0 - 2026-08-18

### Added

- Packaged fresh-start account provisioning with `chatvoice accounts add/list`, using environment-provided passwords and the same SQLite runtime database as the web service.
- Web settings API Token panel for signed-in users: create, list, and revoke token metadata while showing token values only once.
- Server-side `api_tokens` SQLite table storing token hash, prefix, scopes, creation time, optional expiry, revocation time, and last-used time.
- Bearer-token data endpoints for automation: `GET /api/data/meetings[/<id>]` and `GET /api/data/conversations[/<id>]`.
- CLI data export commands: `chatvoice data meetings`, `chatvoice data meeting`, `chatvoice data conversations`, and `chatvoice data conversation`.
- Importable HTTP client helpers in `chatvoice.client` so CLI handlers stay thin.
- API access documentation covering browser token generation, CLI token lifecycle, and fresh-start data reads.

### Changed

- Version bumped from `0.0.2` to `0.1.0` for the first minor release.
- README, MkDocs deployment guide, CLI tree, capability map, and interface tree now document the full install → account → service → token → data-read flow.
- Source readiness messages now describe the v0.1.0 SQLite concurrency boundary.

### Notes

- SQLite WAL remains the packaged storage backend and should run with one service process. Postgres/MySQL storage migration remains a separate release task for high-concurrency deployment.
- API tokens are read-only for data export; they do not write meetings, edit summaries, or manage accounts.
- Raw recording blobs remain browser-local for meeting-history download and are not returned by data APIs.

## 0.0.2 - 2026-08-18

### Added

- Packaged Speakr FastAPI/browser app entrypoint: `chatvoice serve app`.
- Runtime path APIs and CLI readback under ChatArch home: `chatvoice paths` and `chatvoice service plan`.
- ASR API provider configuration for `api-server`, the ASR API URL setting, and an optional server-side credential setting.
- Health and doctor commands: `chatvoice health status`, `chatvoice doctor`, and `chatvoice asr channels`.
- MkDocs deployment guide covering PyPI install, service startup, API-first GPU ASR server integration, and SQLite concurrency boundary.

### Changed

- Version bumped from the `0.0.1` placeholder to `0.0.2` patch release.
- CI now installs the `web` extra so packaged FastAPI app smoke tests run on GitHub.
- Docs dependency bounds allow current MkDocs Material 9.x while staying below the next major line.

### Notes

- SQLite WAL is the v0.0.2 packaged storage backend and should run with one service process. Postgres/MySQL storage migration remains a separate release task for high-concurrency deployment.
- GPU ASR should normally run behind an API provider/server; local FunASR channels remain compatibility modes.
