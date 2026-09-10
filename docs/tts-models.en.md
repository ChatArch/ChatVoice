# Speech Synthesis Backends

System TTS and the cloned voice share the voice-studio text composer but use separate backends. The server supplies the voice catalog; users select labels rather than entering IDs.

| Protocol | `CHATVOICE_TTS_API_TYPE` | Requirement |
| --- | --- | --- |
| OpenAI-compatible speech | `openai` | Provider supporting `/audio/speech` |
| Volcengine unidirectional streaming | `volcengine` | Resource ID and supported voices |
| Qwen WebSocket | `qwen-ws` | Compatible endpoint, model entitlement and Plan credentials |

## OpenAI-compatible example

```dotenv
CHATVOICE_TTS_API_TYPE=openai
CHATVOICE_TTS_API_BASE=https://speech.example.com/v1
CHATVOICE_TTS_API_KEY=[REDACTED]
CHATVOICE_TTS_MODEL=your-tts-model
CHATVOICE_TTS_VOICES='[{"id":"voice-id","label":"Default voice"}]'
```

Replace every placeholder. The voice catalog is a JSON array; its first entry is the default. Labels are displayed and IDs are sent to the provider.

## Other protocols

Volcengine also requires `CHATVOICE_TTS_RESOURCE_ID`. `API_BASE` may contain the full `/api/v3/tts/unidirectional` path, or the adapter appends it. Model and resource ID are different settings.

Qwen WebSocket uses its own compatible endpoint and credential policy. Do not apply that provider's key rules to unrelated protocols, or infer entitlement from model-list visibility.

Any nonempty independent TTS setting enables explicit configuration; partial settings fail. Legacy compatibility is selected only when all independent fields are empty. Text-model credentials are never borrowed.

## Use and verify

1. Open voice studio and select a configured system voice.
2. Enter text, choose an available output format and generate.
3. Verify playback, then download the result.
4. Test voice/format changes separately; one successful example does not establish every protocol.

Provider/model/voice response headers should match the selection. Validate the real container, sample rate and playable audio, not merely its extension. Synthesis probes in `chatenv test -t chatvoice -I` consume provider quota.

[Configuration](configuration.md) · [Voice cloning](voice-cloning.md) · [Troubleshooting](troubleshooting.md)
