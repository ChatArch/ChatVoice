# Offline Operation Regression

## Standard Entry Point

Use an isolated development environment with the project's `dev`, `web`, and `docs` extras, and **Node.js 22 or newer** on `PATH`:

```sh
node --version
python -m pytest tests
```

Playwright, Chromium, a browser, physical microphones, model services, and provider credentials are not required. Missing or outdated Node fails the controller tests instead of silently skipping them. CI configures Node 22 for every Python test job.

Before collection or application imports, `tests/conftest.py` redirects `HOME`, `CHATARCH_HOME`, and `CHATVOICE_HOME` to dedicated temporary paths and restores them afterwards. Temporary allocation honors standard `TMPDIR`. Do not install test dependencies or run acceptance in a production runtime. Route tests additionally allocate a separate SQLite database per case.

Run the operation matrix directly:

```sh
python -m pytest tests/test_nonbrowser_flows.py tests/test_nonbrowser_routes.py -q
```

## Flow-to-Test Mapping

Controller names below are parameter IDs of `test_nonbrowser_controller_flow`. Route tests live in `tests/test_nonbrowser_routes.py`.

| Operation | Executed coverage |
| --- | --- |
| Login, logout, guest, session expiry, CSRF | `access-*` executes login and logout handlers. `test_account_record_token_session_lifecycle` exercises real ASGI login rejection, cookies, CSRF, logout, expired-session removal, and two-account record isolation. |
| API tokens and one-time output | `token` executes creation, clipboard output, and settings closure. The route lifecycle verifies creation-only plaintext, Bearer data access, and 401 after revocation. `test_api_tokens.py` adds scopes and expiry boundaries. |
| Record, pause, resume, finish | `recording-{connecting,recording,paused,finishing}-{reset,new,delete}` executes registered handlers and checks socket, tracks, audio graph, animation/timer cleanup and old ASR callbacks. `asrFinish` verifies revision merging, commit acknowledgement, final persistence, and summary generation. |
| Meeting create/save/reopen/title/tags/search/copy/clear/delete | `meeting`, `title-*`, and `recording-*-reset` execute actual controllers and persistence functions against an isolated IndexedDB boundary. The ASGI lifecycle verifies authenticated persistence. |
| Notes, titles, SSE revisions, four presets, undo, canvas editing/copy | `summary-*`, `title-*`, `revision-*`, and `lateRevision` assert content, saved records, busy/readOnly recovery, HTTP-200 SSE errors, missing done, empty summaries, and late-result rejection. `test_text_routes_finish_and_failure` runs actual routes and text adapters through success/error/truncation and response closure. |
| System TTS | `tts-*` covers dynamic voice selection, MP3/WAV, short/long/empty text, object URLs, downloads, error/timeout/empty-audio recovery, and explanatory disabled configuration states. `test_tts_api.py` and `test_tts_qwen.py` cover defaults, protocols, invalid audio, truncation, and resource closure; `test_tts_web.py` covers HTTP dispatch and headers. |
| One-shot cloning | `clone-*` executes upload change and reference recording handlers, account/reference/consent prerequisites, generation, timer-driven polling, downloads, failed jobs, stale creation/status/audio results, reference URL and polling cleanup, and clone selection preservation on refresh; no voice history is created. `test_clone_routes_lifecycle` checks authorization, CSRF, empty/oversized/upstream-rejected audio, failed jobs, audio download, and temporary-job deletion. |
| Realtime conversation | `realtime-*` exercises input PCM, text requests, transcript merging, output PCM scheduling, mute/unmute, stop, Markdown export, history save/reopen/delete, and connection/device failure cleanup. `test_realtime_asgi_protocol_and_cleanup` runs the actual WebSocket route with bidirectional frames, text/audio conversion, `session.created` forwarding, invalid models, and upstream failure. |
| Navigation, products, settings, tabs, help | `navigation` executes switching and settings handlers and asserts hidden panels, active product, recording-time switch restrictions, active tab, dialog state, and external-link target attributes—not pixel positions. |

## Boundaries

- The Node VM loads the shipped inline controller and `transcript-state.js`, including real event registration. Only automatic page-tail startup is omitted; tests invoke entries explicitly. Business logic is not copied, and render/state/persistence functions are not replaced.
- The minimal DOM, IndexedDB, fetch, WebSocket, MediaRecorder, AudioContext, clipboard, object URLs, and timers are offline boundary fakes. Assertions inspect actual state, rendered output, saved records, and download descriptors, not just call counts. Asynchronous work uses bounded predicate barriers; tests explicitly advance polling timers.
- ASGI tests retain routing, validation, authentication, serialization, SQL, and text adapters. Upstream/device boundaries are fake. To avoid sandbox thread-notification stalls, the fixture's thread executors and synchronous-stream iterators execute the original functions/generators sequentially. This does not test thread scheduling or concurrency performance. WebSocket tests use in-memory ASGI messages without listening ports.
- `mutations` removes the SSE error branch and corrupts download-format selection in memory. The same business assertions must reject both mutations; no working-tree mutation occurs. Existing substring contract tests remain useful but do not count as executed flow coverage.
- Exclusions: pixels/layout, actual DOM-engine behavior, browser IndexedDB transaction scheduling, physical microphone permissions, audible playback, real audio decoding, provider connectivity, billing, and deployment health. Reference recordings use synthetic Blobs; adapter tests supplement audio validation.

## Explicit Live Gate

The repository includes a separate browser-free deployed-route verifier (httpx/websockets plus system ffmpeg/ffprobe required):

```sh
python scripts/verify_service.py --live \
  --url https://voice.example.com \
  --out <project>/playground/live-check \
  --asr-audio <synthetic-mono-pcm16-16khz.wav> \
  --realtime
```

It checks deployed UI defaults, title/notes/four revisions, every configured voice in MP3/WAV, default text, and empty-input rejection. Revisions require exactly one ordered canvas/reply marker pair and nonempty canvas and reply. TTS requires provider/model/voice headers matching status and request, format-specific MIME, successful ffmpeg decoding, and ffprobe container/codec matching MP3 or PCM16 WAV. Receipts record the observed identity and audio format. No browser or meeting-record mutation is used.

Optional ASR reads the default channel and engine from `/api/asr/channels` and rejects stub/mock configuration before sending audio. Use a nonempty synthetic mono PCM16 16 kHz WAV of **at most three seconds** (file size at most 256,000 bytes); longer fixtures are deliberately outside this two-commit check. The ready/started context must exceed the fixture duration to prevent automatic rollover. Ready, started and result channels and result engine must match configuration. Each segment needs its own nonempty final result, with windows 1 then 2, increasing chunk/revision IDs, and matching commit/finish rollover and done-window metadata. Receipts retain per-segment metadata, rather than claiming unconditional real provider calls.

Optional realtime validates the acknowledged model, voice, modalities, audio formats, instructions, history limit and turn detection. It permits exactly one requested active response, correlates created/done IDs and forwarded response events, and requires explicit `completed` status plus nonempty text/audio. Derived events without IDs are accepted only during that single active response; forwarded upstream events still undergo ID checks. This is transport evidence, not independent provider attestation or a successful-handshake shortcut.

Add `--clone-reference <synthetic.wav>` with a dedicated, administrator-provisioned `qa-verify-` account in `CHATVOICE_VERIFY_ACCOUNT` and `CHATVOICE_VERIFY_PASSWORD` (custom variable names via `--account-env` / `--password-env`). Only the completed job created by this invocation is deleted, with 404 readback, followed by verified logout. A still-running timed-out job is retained with its exact ID for safe follow-up. The administrator removes the disposable account afterward.

Each case is persisted in `receipt.json`. Failed, missing or blocked coverage exits nonzero; optional selection is explicit in `selected_optional_flows`. There are no automatic generation retries, provider/config changes, or paid fallbacks. `--live` consumes the configured Plan's actual resources and requires billing authorization. `AccessDenied.Unpurchased` is a subscription/permission blocker, not a healthy session.

`test_live_acceptance_contract.py` checks SSE termination, empty output, origins, cleanup IDs and exit semantics. `test_live_exchanges.py` executes the actual verifier with HTTP/WebSocket and ffmpeg/ffprobe process-boundary fakes, including wrong/missing identities, ASR resumed-result attribution, realtime acknowledgement/response correlation, revision marker failures and blocked Plan denial. No verifier business functions are replaced; sockets are denied. Process fakes do not establish real audio decoding. `test_realtime_provider_errors.py` covers flat provider errors and preserving their actionable message after socket closure.

Offline success does not establish provider connectivity, subscription validity, or audible output. Real HTTP/SSE/WebSocket acceptance requires separate explicit authorization, controlled environments, synthetic data, and no user-record access. Record `PASS`, `FAIL`, `BLOCKED`, and `NOT_RUN` separately. Never turn ordinary pytest into live provider probing or substitute browser clicking for these business regressions.

If older `TestClient` cases stall in a sandbox, preserve the exact case, timeout exit code, and stack trace, report full-suite verification as blocked, and rerun in an authorized environment. A timeout is not a passing full suite.
