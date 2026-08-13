# Qwen Token Plan Audio Demo

A lightweight FastAPI + browser demo for Qwen Token Plan audio capabilities plus a pluggable ASR panel.

## Features

- **TTS**: server-side proxy for `qwen-audio-3.0-tts-plus`, returning playable MP3/WAV audio.
- **Realtime communication**: browser WebSocket -> FastAPI proxy -> Qwen `qwen-audio-3.0-realtime-plus` Realtime WebSocket.
- **ASR transcription**: multi-channel ASR contract with `funasr-cpu` and `stub-local`; ASR results are normalized into one public transcript board.
- **Transcript board**: final/corrected text is primary; raw/interim text is shown as a small note to avoid duplicate-looking output.

## Security model

- The browser never receives or stores the Qwen API key.
- Set the key only on the server via `OPENAI_API_KEY` or `DASHSCOPE_API_KEY`.
- Optional local env-file loading is available with `QWEN_TOKEN_PLAN_ENV_FILE=/path/to/local.env`.
- Do not commit real `.env` files, model caches, probe output, audio files, or runtime logs.

## Quick start

```bash
cd qwen-audio-tts-realtime-demo
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY='[REDACTED]'
export OPENAI_API_BASE='https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
uvicorn app.main:app --host 127.0.0.1 --port 18087
```

Open:

```text
http://127.0.0.1:18087/
```

For remote development, use an SSH tunnel or a properly protected reverse proxy. Keep the API key server-side.

## Optional env file

```bash
cp .env.example .env.local
# edit .env.local locally; never commit it
export QWEN_TOKEN_PLAN_ENV_FILE="$PWD/.env.local"
uvicorn app.main:app --host 127.0.0.1 --port 18087
```

## Optional FunASR CPU environment

The main app can run without FunASR installed; `stub-local` still exercises the upload/recording -> raw/corrected -> transcript-board contract. For the real `funasr-cpu` channel:

```bash
uv venv .venv-asr --python python3.11
uv pip install --python .venv-asr/bin/python --index-url https://download.pytorch.org/whl/cpu torch torchaudio
uv pip install --python .venv-asr/bin/python funasr modelscope soundfile
```

Model cache is written to `playground/model-cache/`, which is ignored by Git.

## API surface

- `GET /api/status`: redacted backend status, models, ASR channels, and route shapes.
- `POST /api/tts`: JSON `{text, voice, format}` -> `audio/mpeg` or `audio/wav`.
- `GET /api/asr/channels`: available ASR channels; default is `funasr-cpu`.
- `POST /api/asr`: multipart upload with `channel=funasr-cpu|stub-local` and `correct=true|false`; returns `raw_text`, `corrected_text`, and a transcript-board event.
- `WS /ws/realtime`: browser-to-backend Realtime proxy; upstream events are normalized into `demo_event=transcript.delta` for the transcript board.

## Verification

```bash
python3 scripts/check_transcript_extraction.py
python3 scripts/check_asr_contract.py
python3 scripts/smoke_asr_api.py --port 18097
```

`smoke_demo.py` also exercises `/api/status`, `/api/tts`, and `/ws/realtime`, but it requires a valid server-side Token Plan key:

```bash
python3 scripts/smoke_demo.py --port 18087
```

Browser-side regression helpers are available for manual dogfood:

```javascript
window.__demoInjectTranscript('hello transcript board')
window.__demoInjectDuplicateScenario()
window.__demoInjectAsrScenario()
```

## Known boundaries

- The Token Plan TTS route is not OpenAI `/audio/speech`; this demo uses the official Token Plan WebSocket SDK path for TTS.
- `qwen-audio-3.0-realtime-plus` is a realtime voice conversation model, not a dedicated pure-ASR model.
- FunASR/SenseVoiceSmall can run CPU-first for low concurrency; production concurrency or low-latency streaming needs separate benchmarking.
