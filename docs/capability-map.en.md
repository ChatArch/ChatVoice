# Capability Map

This page checks the first-class capabilities currently owned by `ChatVoice`, their verification state, and current boundaries.

## Current capabilities

<div class="grid cards" markdown>

- **Packaged web service**

    Installing `ChatVoice[web]` lets operators start the current Speakr FastAPI + browser service with `chatvoice serve app`.

- **Fresh-start accounts and API tokens**

    `chatvoice accounts add` creates invited accounts in the packaged runtime database. Signed-in users can create one-time-visible API tokens from the web settings panel; the CLI can also create/list/revoke token metadata.

- **Data read API / CLI**

    `GET /api/data/...` and `chatvoice data ...` use bearer tokens to read meeting transcripts, meeting summaries, and realtime conversation text records.

- **API-first ASR provider**

    The production direction is `api-server`: the backend calls a managed ASR API or self-hosted GPU ASR server over HTTP instead of embedding GPU runtime in the web process.

- **Runtime paths and service plan**

    `chatvoice paths` and `chatvoice service plan` read back data, log, run, temp, and model-cache paths under ChatArch home.

- **Health checks**

    `chatvoice health status` reads `/api/status` from a running service.

</div>

## Status table

| Capability | Status | Notes |
| --- | --- | --- |
| Base CLI entries | Implemented | `--help`, `--version`, and `--tree`. |
| Runtime paths | Implemented | Default `<chatarch-home>/chatvoice/`, override with runtime-home overrides. |
| Packaged web startup | Implemented | `chatvoice serve app` calls `chatvoice.web.server:create_app`. |
| Invited account CLI | Implemented | `chatvoice accounts add/list`; passwords are read from environment variables only. |
| API token management | Implemented | Web settings panel + CLI token lifecycle; the server stores hashes only. |
| Data read API/CLI | Implemented | Bearer token reads for meetings, summaries, and realtime conversations. |
| ASR API provider | Implemented | `CHATVOICE_ASR_CHANNEL=api-server` + the ASR API URL setting. |
| Local contract smoke | Implemented | `CHATVOICE_ASR_CHANNEL=stub-local` starts the full path without GPU/cloud credentials. |
| Local FunASR compatibility | Preserved | `funasr-gpu` / `funasr-cpu` remain available, but production should prefer an external ASR API server. |
| SQLite WAL storage | Implemented | Default for one service process and light concurrency; the `api_tokens` table stores only hash/prefix/metadata. |
| Postgres/MySQL storage | Not implemented | External URLs are detected in plan/doctor, but v0.1.7 packaged legacy storage still supports SQLite only. |

## Out of scope now

- Do not bundle GPU model download, CUDA/PyTorch installation, and the web process as one default runtime.
- Do not claim MySQL/Postgres is complete in v0.1.7; high-concurrency storage migration needs a separate release.
- Do not print tokens, cookies, Authorization headers, or raw recordings; full transcripts are returned only by explicit data-read commands.
- Do not manage services with `kill` / `kill -9`; restart commands need supervisor/graceful boundaries first.
