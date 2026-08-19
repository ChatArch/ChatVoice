# Changelog

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
