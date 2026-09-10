# Voice Cloning

Cloning is a one-shot workflow: generate new speech from target text using an authorized reference. It does not create a permanent voice profile.

| Prerequisite | Requirement |
| --- | --- |
| Account | Invited account login; guests cannot submit clone jobs |
| Reference | Clear speech from yourself or an explicitly authorized source |
| Consent | Confirm voice-use permission in the page |
| Backend | Reachable compatible VoiceClone sidecar |
| Input | Target text, language and speed control |

## Generate in voice studio

1. Open voice studio and select the cloned-voice card in the shared voice picker.
2. Upload a reference or use the reference-recording control.
3. Confirm permission and enter target text in the shared composer.
4. Adjust language/speed if needed and generate.
5. Wait for model loading and synthesis, preview the result, then download.

The reference is reusable within the current session. Cold starts take longer; do not submit duplicate jobs. Read the visible explanation when account, reference, permission, text or backend readiness is missing.

## Connect the sidecar

ChatVoice does not install the model or GPU runtime. Prepare a verified independent sidecar first:

```dotenv
CHATVOICE_VOICECLONE_URL=http://127.0.0.1:18187
CHATVOICE_VOICECLONE_TIMEOUT_SECONDS=600
```

Use loopback when co-located, or a reachable controlled LAN address across hosts. Keep IndexTTS outside the ChatVoice web environment. IndexTTS 2.5 requires its own Python 3.11 environment and complete model directory; auxiliary models alone are insufficient.

A compatible sidecar provides `/health`, job creation/query/deletion under `/v1/jobs`, and job audio. ChatVoice adds account ownership and CSRF at its proxy. Do not expose the unauthenticated sidecar to an uncontrolled public network.

## Health is not generation

| State | Meaning |
| --- | --- |
| `configured=false` | No configured endpoint |
| `status=offline` | Backend currently unreachable |
| `status=ready`, `model_loaded=false` | Reachable service, model not yet loaded |
| `status=ready`, `model_loaded=true` | Loaded; real generation still needs verification |

`/api/voice-clone/status` returns flat JSON. Acceptance should create a real job with an authorized reference, download/decode the audio, optionally compare it through ASR, then delete the test job and confirm it is unavailable.

Use durable supervision and graceful shutdown for persistent services. Verify enabled state, process and logs. Restarting the web app cannot restore a sidecar lost with a temporary session.

## Retention and access

Results serve the current preview/download, not a generation history or permanent voice library. Page departure and expiry participate in cleanup; downloaded copies have their own lifecycle. Only the owning account can read or delete the job through ChatVoice.

[HTTP API](api-access.md) · [Retention](recording-storage.md) · [Offline diagnosis](troubleshooting.md#voiceclone)
