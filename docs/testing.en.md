# Testing and Acceptance

Offline regressions, real-provider checks and visual acceptance are separate evidence layers.

| Layer | Coverage | Real external service |
| --- | --- | --- |
| Python units/routes | Config, auth, storage, model boundaries, backup | No; boundary fakes |
| Non-browser frontend | Actual controllers, events, cancellation, late results, cleanup | No; device/network fakes |
| Real service | Model output, persistence readback, actual audio | Yes |
| Visual/device | Desktop/mobile layout, microphone, playback, download | Yes, as scoped |

## Local regression

Install development dependencies and Node.js, which is required by frontend-controller tests.

```bash
python -m pip install -e ".[web,dev,docs]"
python -m pytest tests -q
chatvoice --tree
mkdocs build --strict
python -m build
python -m twine check dist/*
```

Tests isolate accounts and databases. Do not inject production HOME, database paths or credentials. Start new business behavior with a failing regression; fake device/model/network boundaries rather than implementing a parallel test-only business flow.

## Regression priorities

- Ownership, CSRF, token scopes and old-record compatibility.
- Recording start/pause/resume/finish and destructive-action resource cleanup.
- Source preservation, persistence, undo and late-result isolation for notes/Todo.
- TTS protocol/format/voice settings and clone upload/state/download/cleanup.
- Real stream completion markers; an unresolved Promise is not a passing test.

## Real service

The source distribution includes a separate verifier; inspect its current options first:

```bash
python scripts/verify_service.py --help
```

Use disposable accounts, authorized/synthetic reference audio and short text. Distinguish PASS, FAIL, BLOCKED and NOT_RUN. Keep per-case responses, visible results and cleanup evidence. Do not change billing policy or swap unrelated models simply to make a test pass.

After deployment, verify version/process, database, warm ASR and text/audio outputs at the real public entry. Cloning needs a real job and decodable audio; health alone establishes reachability.

[Deployment](deployment.md) · [Troubleshooting](troubleshooting.md)
