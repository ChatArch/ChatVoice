# Changelog

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
