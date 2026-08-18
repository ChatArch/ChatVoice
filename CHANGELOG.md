# Changelog

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
