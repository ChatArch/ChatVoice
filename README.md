# Qwen Token Plan Audio Demo

A lightweight FastAPI + browser meeting recorder with realtime transcription, local audio capture, and AI meeting notes. The existing Qwen Token Plan audio and GPU-first ASR APIs remain available behind the product UI.

## Features

- **语音合成 (TTS)**: server-side proxy for `qwen-audio-3.0-tts-plus`, returning playable MP3/WAV audio.
- **声音克隆**: server-side DashScope TTS v2 voice enrollment (`VoiceEnrollmentService`) creates reusable `voice_id` values; the browser never sees the API key.
- **实时对话**: browser WebSocket -> FastAPI proxy -> Qwen `qwen-audio-3.0-realtime-plus` Realtime WebSocket.
- **会议录音首页**: a mobile-first recording surface with live transcript, waveform, pause/resume, finish, and local audio download.
- **语音转写**: the recorder streams microphone PCM16 to the existing ASR WebSocket and appends normalized final segments to the timeline.
- **GPU-first ASR**: default ASR channel is `funasr-gpu` (CUDA PyTorch + FunASR/SenseVoiceSmall worker). `funasr-cpu` remains an explicit fallback, and `stub-local` remains available for smoke tests.
- **Realtime ASR WebSocket**: `WS /ws/asr/stream` accepts continuous PCM16 microphone frames and returns `demo_event=asr.stream.result` events that the page appends into the chat input composer.
- **会议纪要**: final transcript segments can be sent to a server-side Qwen-compatible model for summary, action items, risks, and open questions.
- **Focused product UI**: the default page exposes exactly two product tabs, `文字记录` and `实时摘要`; TTS, voice cloning, and realtime conversation stay available as backend capabilities for later product work.

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
# Set OPENAI_API_KEY or DASHSCOPE_API_KEY in the server environment first.
# Keep credentials out of the browser, repository, logs, and shell history.
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

Real GPU ASR uses an ignored project-local GPU venv. For low-latency streaming, install the web dependencies in the same venv and run Uvicorn with it so the model remains cached in process:

```bash
python3 -m venv .venv-asr-gpu
.venv-asr-gpu/bin/python -m pip install --upgrade pip setuptools wheel
.venv-asr-gpu/bin/python -m pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
.venv-asr-gpu/bin/python -m pip install funasr modelscope soundfile scipy librosa pydub ffmpeg-python
.venv-asr-gpu/bin/python -m pip install -r requirements.txt
.venv-asr-gpu/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 18087
```

Running the web service from the lightweight `.venv` remains supported through the subprocess worker fallback, but each chunk may pay model startup cost and is not recommended for interactive use.

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
- `POST /api/asr`: programmatic/smoke multipart upload endpoint with `channel=funasr-gpu|funasr-cpu|stub-local` and `correct=true|false`; not the browser ASR product flow.
- `WS /ws/asr/stream`: bounded continuous PCM16 ASR stream used by the browser one-button realtime transcription UI; returns `demo_event=asr.stream.result` with normalized transcript events.
- `WS /ws/realtime`: browser-to-backend Realtime proxy; upstream events are normalized into `demo_event=transcript.delta` for the Realtime board.
- `POST /api/meeting-notes/polish`: Qwen-compatible chat completion endpoint for transcript polish + realtime summary structure.

### Public ASR stream limits

`/ws/asr/stream` is intentionally bounded for a public demo:

- accepted sample rates are `8000`, `16000`, `24000`, and `48000` Hz;
- one websocket audio frame is capped at 256 KiB of PCM16 data;
- one JSON/base64 frame is capped at 384 KiB;
- one connection can buffer at most 20 seconds and send at most 60 seconds of PCM16 audio;
- each receive cycle processes at most two ASR chunks and reports backpressure if more decoded audio is queued;
- per-chunk temporary WAV/upload files under `playground/asr-temp/` are cleaned after each ASR attempt.

## Verification

```bash
python3 scripts/check_ui_contract.py
python3 scripts/check_transcript_extraction.py
python3 scripts/check_asr_contract.py
python3 scripts/check_asr_gpu_contract.py
python3 scripts/smoke_asr_api.py --port 18097
python3 scripts/check_meeting_e2e.py --base-url http://127.0.0.1:18087
```

`smoke_demo.py` also exercises `/api/status`, `/api/tts`, and `/ws/realtime`, but it requires a valid server-side Token Plan key:

```bash
python3 scripts/smoke_demo.py --port 18087
```

Browser-side regression helpers are available for manual dogfood:

```javascript
window.__demoInjectAsrScenario()
window.__demoInjectSummary()
window.__demoGetState()
```

## Known boundaries

- The Token Plan TTS route is not OpenAI `/audio/speech`; this demo uses the official Token Plan WebSocket SDK path for TTS.
- `qwen-audio-3.0-realtime-plus` is a realtime voice conversation model, not a dedicated pure-ASR model.
- Voice cloning requires a reference audio URL that DashScope can fetch from the server side.
- GPU FunASR first-run model download/warm-up can be slow; keep `stub-local` for fast public smoke and CI-like contract checks.
