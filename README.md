# Qwen Token Plan Audio Demo

A lightweight FastAPI + browser demo for Qwen Token Plan audio capabilities plus a GPU-first ASR/meeting-notes panel.

## Features

- **TTS**: server-side proxy for `qwen-audio-3.0-tts-plus`, returning playable MP3/WAV audio.
- **voice cloning**: server-side DashScope TTS v2 voice enrollment (`VoiceEnrollmentService`) creates reusable `voice_id` values; the browser never sees the API key.
- **realtime communication**: browser WebSocket -> FastAPI proxy -> Qwen `qwen-audio-3.0-realtime-plus` Realtime WebSocket.
- **ASR transcription**: default ASR channel is `funasr-gpu` (CUDA PyTorch + FunASR/SenseVoiceSmall worker). `funasr-cpu` remains an explicit fallback, and `stub-local` remains available for smoke tests.
- **chunked realtime transcription**: `WS /ws/asr/stream` accepts PCM16 audio chunks, converts them to WAV chunks, and sends results back as transcript-board events.
- **meeting notes**: ASR transcript text can be sent to a server-side Qwen-compatible chat model for AI polish, repaired meeting notes, summary, action items, risks, and open questions.
- **Separated tabs**: the browser has exactly three isolated tabs: `TTS`, `realtime communication`, and `ASR transcription`. Realtime and ASR have separate transcript boards.
- **Readable transcript display**: final/corrected text is primary; raw/interim text is only a small aside and is deduped so one utterance does not look like two dialogue turns.

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

## GPU ASR environment

The main service venv stays lightweight. Real GPU ASR runs through an ignored project-local worker venv:

```bash
python3 -m venv .venv-asr-gpu
.venv-asr-gpu/bin/python -m pip install --upgrade pip setuptools wheel
.venv-asr-gpu/bin/python -m pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
.venv-asr-gpu/bin/python -m pip install funasr modelscope soundfile scipy librosa pydub ffmpeg-python
```

Recommended server env:

```bash
export DEFAULT_ASR_CHANNEL=funasr-gpu
export FUNASR_GPU_DEVICE=cuda:0
export FUNASR_MODEL=iic/SenseVoiceSmall
```

Model cache is written to `playground/model-cache/`, which is ignored by Git.

## API surface

- `GET /api/status`: redacted backend status, models, ASR channels, and route shapes.
- `POST /api/tts`: JSON `{text, voice, format}` -> `audio/mpeg` or `audio/wav`.
- `POST /api/voice-cloning/create`: JSON `{audio_url, prefix, target_model, language_hints}` -> server-created `voice_id`.
- `GET /api/voice-cloning/list`: list server-side voice enrollment ids by prefix.
- `GET /api/asr/channels`: available ASR channels; default is `funasr-gpu`.
- `POST /api/asr`: multipart upload with `channel=funasr-gpu|funasr-cpu|stub-local` and `correct=true|false`; returns `raw_text`, `corrected_text`, and a transcript-board event.
- `WS /ws/asr/stream`: chunked PCM16 ASR stream; returns `demo_event=asr.stream.result` with normalized ASR board events.
- `WS /ws/realtime`: browser-to-backend Realtime proxy; upstream events are normalized into `demo_event=transcript.delta` for the Realtime board.
- `POST /api/meeting-notes/polish`: Qwen-compatible chat completion endpoint for transcript polish + realtime summary structure.

## Verification

```bash
python3 scripts/check_ui_contract.py
python3 scripts/check_transcript_extraction.py
python3 scripts/check_asr_contract.py
python3 scripts/check_asr_gpu_contract.py
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
- Voice cloning requires a reference audio URL that DashScope can fetch from the server side.
- GPU FunASR first-run model download/warm-up can be slow; keep `stub-local` for fast public smoke and CI-like contract checks.
