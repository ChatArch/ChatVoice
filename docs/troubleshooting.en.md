# Troubleshooting

Separate user entry, business processing and external models before restarting components.

| Symptom | Inspect first | Reference |
| --- | --- | --- |
| Page/microphone unavailable | Actual URL, HTTPS, browser permission | [Web guide](web-guide.md) |
| Summary/Todo failure | Purpose-specific settings, 502/503, quota | [Text models](text-models.md) |
| TTS catalog/generation failure | Independent TTS settings and audio format | [Speech backends](tts-models.md) |
| Clone backend offline | Configured address, listener and supervisor | [Clone diagnosis](#voiceclone) |
| Missing record after refresh | Account/guest mode, origin and save state | [Retention](recording-storage.md) |
| Read-only API denied | Scope, expiry, revocation, ownership | [HTTP API](api-access.md) |

## Read actual state

```bash
chatvoice doctor --json
chatvoice health status --url https://speakr.example.com --json
```

Database readiness in `/api/heartbeat` is `database.ok`; ASR warm state is `asr.funasr_model_warm`. Do not check nonexistent top-level aliases.

`/api/status` and model visibility do not establish generation, quota or entitlement. Record request time, route, HTTP status and sanitized errors, not raw credentials.

## Notes and Todo

- `503`: inspect the current purpose's independent settings, not unrelated TTS/ASR.
- `502`: distinguish upstream rejection, network errors and empty/truncated output; preserve source text.
- Browser fetch failure with a successful equivalent HTTP request: inspect browser network, proxy and timeouts before blaming credentials.
- Incomplete conversations/SSE without a terminal marker must not overwrite the document as a successful result.

Use the actual supervisor log, for example:

```bash
journalctl --user -u chatvoice.service -n 100 --no-pager
```

Logging depends on the launcher. A `logs/` directory does not imply complete upstream error-body capture.

## Clone backend offline {#voiceclone}

1. Read `CHATVOICE_VOICECLONE_URL` to identify the real host and port.
2. Request its `/health` from the main-service host, not only sidecar loopback.
3. Check the listener, runtime, complete model directory and existing supervisor.
4. If a temporary session disappeared, reuse its environment under durable supervision. Do not reinstall all GPU dependencies or restart the web app unnecessarily.
5. Run an authorized test job, confirm `model_loaded=true`, decode audio and remove the job.
6. Read ChatVoice `/api/voice-clone/status`: expect `configured=true` and `status=ready`.

`model_loaded=false` may mean a cold start rather than an offline service. Inspect state before deciding to restart.

## Storage and identity

Guest records belong to the current browser and are not uploaded automatically. After refresh, select the appropriate mode if prompted. For accounts, verify the signed-in identity and meeting. A read-only token cannot substitute for Cookie/CSRF when saving.

[Deployment/upgrades](deployment.md) · [Testing](testing.md)
