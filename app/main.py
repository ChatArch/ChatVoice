from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import dashscope
from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

try:
    import websockets
except Exception:  # pragma: no cover
    websockets = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "app" / "static"
PROFILE_ENV_FILE = os.getenv("QWEN_TOKEN_PLAN_ENV_FILE", "").strip()
PROFILE_PATH = Path(PROFILE_ENV_FILE).expanduser() if PROFILE_ENV_FILE else None
TOKEN_PLAN_TTS_WS = "wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
TOKEN_PLAN_REALTIME_WS = "wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime"
REALTIME_MODEL = "qwen-audio-3.0-realtime-plus"
TTS_MODEL = "qwen-audio-3.0-tts-plus"
DEFAULT_VOICE = "longanlingxin"
DEFAULT_ASR_CHANNEL = "funasr-cpu"
ASR_CHANNELS: dict[str, dict[str, Any]] = {
    "funasr-cpu": {
        "label": "FunASR CPU（SenseVoiceSmall / Paraformer，可替换）",
        "engine": "funasr",
        "device": "cpu",
        "status": "lazy-load",
        "notes": "真实 FunASR 通道；依赖未安装时返回明确错误，不影响页面其它功能。",
    },
    "stub-local": {
        "label": "本地合同通道（无模型，用于体验/回归）",
        "engine": "stub",
        "device": "cpu",
        "status": "ready",
        "notes": "用于先打通上传/录音→raw/corrected→公屏体验，不代表识别质量。",
    },
}

app = FastAPI(title="Qwen Token Plan Audio + Multi-channel ASR Demo", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost", "http://127.0.0.1:18087", "http://localhost:18087"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=800)
    voice: str = Field(DEFAULT_VOICE, min_length=1, max_length=80)
    format: str = Field("mp3", pattern="^(mp3|wav)$")


def _read_profile() -> dict[str, str]:
    data: dict[str, str] = {}
    if PROFILE_PATH and PROFILE_PATH.exists():
        for raw in PROFILE_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key] = value.strip().strip('"').strip("'")
    # Allow explicit env override for a temporary shell session, but never expose it.
    for key in ("OPENAI_API_KEY", "OPENAI_API_BASE", "DASHSCOPE_API_KEY"):
        if os.getenv(key):
            data[key] = os.environ[key]
    return data


def _token_plan_key() -> str:
    profile = _read_profile()
    key = profile.get("OPENAI_API_KEY") or profile.get("DASHSCOPE_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="Missing Token Plan API key. Set OPENAI_API_KEY or DASHSCOPE_API_KEY on the server.")
    return key


def _token_plan_base() -> str:
    profile = _read_profile()
    return profile.get("OPENAI_API_BASE", "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1").rstrip("/")


def _safe_profile_summary() -> dict[str, Any]:
    profile = _read_profile()
    key = profile.get("OPENAI_API_KEY") or profile.get("DASHSCOPE_API_KEY") or ""
    base = profile.get("OPENAI_API_BASE", "")
    parsed = urlparse(base) if base else None
    return {
        "profile": "env-or-optional-file",
        "profile_file_exists": bool(PROFILE_PATH and PROFILE_PATH.exists()),
        "base_host": parsed.netloc if parsed else None,
        "base_path": parsed.path if parsed else None,
        "key_present": bool(key),
        "key_sha256_12": hashlib.sha256(key.encode()).hexdigest()[:12] if key else None,
        "tts_model": TTS_MODEL,
        "realtime_model": REALTIME_MODEL,
        "asr_channels": ASR_CHANNELS,
        "asr_default_channel": DEFAULT_ASR_CHANNEL,
        "asr_contract": "multi-channel raw_text + corrected_text + public-board event",
        "tts_websocket_url_shape": TOKEN_PLAN_TTS_WS.replace("token-plan.cn-beijing.maas.aliyuncs.com", "[HOST]"),
        "realtime_websocket_url_shape": (TOKEN_PLAN_REALTIME_WS + "?model=" + REALTIME_MODEL).replace(
            "token-plan.cn-beijing.maas.aliyuncs.com", "[HOST]"
        ),
    }


def _fetch_models() -> dict[str, Any]:
    key = _token_plan_key()
    url = _token_plan_base() + "/models"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "User-Agent": "qwen-audio-demo/0.1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    ids = [item.get("id") for item in payload.get("data", []) if isinstance(item, dict)]
    return {"count": len(ids), "model_ids": ids}


def _tts_blocking(req: TTSRequest) -> dict[str, Any]:
    key = _token_plan_key()
    dashscope.api_key = key
    dashscope.base_websocket_api_url = TOKEN_PLAN_TTS_WS
    audio_format = AudioFormat.MP3_22050HZ_MONO_256KBPS if req.format == "mp3" else AudioFormat.WAV_24000HZ_MONO_16BIT
    started = time.time()
    synthesizer = SpeechSynthesizer(model=TTS_MODEL, voice=req.voice, format=audio_format)
    audio = synthesizer.call(req.text)
    if not audio:
        raise RuntimeError("TTS returned empty audio")
    return {
        "audio": audio,
        "elapsed_ms": round((time.time() - started) * 1000),
        "request_id": getattr(synthesizer, "get_last_request_id", lambda: None)(),
        "first_package_delay_ms": getattr(synthesizer, "get_first_package_delay", lambda: None)(),
        "sha256_12": hashlib.sha256(audio).hexdigest()[:12],
    }


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.head("/")
def index_head() -> Response:
    return Response(status_code=200, media_type="text/html")


@app.get("/api/status")
def status() -> JSONResponse:
    result = _safe_profile_summary()
    try:
        result["models"] = _fetch_models()
        result["models_ok"] = True
    except Exception as exc:  # keep status page usable if listing fails
        result["models_ok"] = False
        result["models_error"] = type(exc).__name__ + ": " + str(exc)[:300]
    return JSONResponse(result)


@app.post("/api/tts")
async def tts(req: TTSRequest) -> Response:
    text = " ".join(req.text.split())
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")
    safe_req = TTSRequest(text=text, voice=req.voice, format=req.format)
    try:
        result = await asyncio.to_thread(_tts_blocking, safe_req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error_type": type(exc).__name__, "message": str(exc)[:600]}) from exc
    media_type = "audio/mpeg" if req.format == "mp3" else "audio/wav"
    suffix = "mp3" if req.format == "mp3" else "wav"
    headers = {
        "X-Qwen-Model": TTS_MODEL,
        "X-Qwen-Voice": req.voice,
        "X-Qwen-Request-Id": str(result.get("request_id") or ""),
        "X-Audio-Bytes": str(len(result["audio"])),
        "X-Audio-Sha256-12": str(result.get("sha256_12") or ""),
        "X-Elapsed-Ms": str(result.get("elapsed_ms") or ""),
        "Content-Disposition": f'inline; filename="qwen-token-plan-tts.{suffix}"',
    }
    return Response(content=result["audio"], media_type=media_type, headers=headers)


def _collapse_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _simple_chinese_correction(raw_text: str) -> str:
    """Tiny local post-process so raw/corrected UI works before LLM correction is wired."""
    text = _collapse_text(raw_text)
    for filler in ("呃", "嗯", "啊", "额"):
        text = text.replace(filler, "")
    text = text.replace(" ,", "，").replace(" .", "。")
    if text and text[-1] not in "。！？.!?":
        text += "。"
    return text or raw_text


def normalize_asr_result(channel: str, raw_text: str, corrected_text: str | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = _collapse_text(raw_text)
    corrected = _collapse_text(corrected_text or "") or _simple_chinese_correction(raw)
    return {
        "channel": channel,
        "raw_text": raw,
        "corrected_text": corrected,
        "meta": meta or {},
        "board_event": {
            "demo_event": "transcript.delta",
            "role": "user",
            "phase": "final",
            "text": corrected,
            "raw_text": raw,
            "source_type": f"asr.{channel}",
        },
    }


def _write_upload_to_temp(audio_bytes: bytes, filename: str) -> Path:
    suffix = Path(filename or "audio.wav").suffix or ".wav"
    temp_dir = PROJECT_ROOT / "playground" / "asr-temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="qwen-demo-asr-", suffix=suffix, dir=str(temp_dir))
    path = Path(name)
    with os.fdopen(fd, "wb") as fh:
        fh.write(audio_bytes)
    return path


def _convert_to_wav_if_needed(path: Path) -> Path:
    if path.suffix.lower() == ".wav":
        return path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return path
    out = path.with_suffix(".wav")
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000", str(out)],
        check=True,
        timeout=45,
    )
    return out


def _stub_asr(audio_bytes: bytes, filename: str) -> dict[str, Any]:
    seconds: float | None = None
    if filename.lower().endswith(".wav"):
        try:
            with wave.open(_write_upload_to_temp(audio_bytes, filename), "rb") as wf:
                seconds = round(wf.getnframes() / float(wf.getframerate()), 3)
        except Exception:
            seconds = None
    text = "这是本地合同通道：音频已上传，ASR 多渠道页面和公屏链路已打通。"
    return normalize_asr_result("stub-local", text, text, {"engine": "stub", "audio_bytes": len(audio_bytes), "seconds": seconds})


def _strip_sensevoice_tags(text: str) -> str:
    """Remove SenseVoice control tags like <|zh|><|NEUTRAL|><|Speech|><|withitn|>."""
    return _collapse_text(re.sub(r"<\|[^|>]+\|>", "", text or ""))


def _extract_funasr_text(result: Any) -> str:
    if isinstance(result, str):
        return _strip_sensevoice_tags(result)
    if isinstance(result, dict):
        for key in ("text", "raw_text"):
            value = result.get(key)
            if isinstance(value, str) and value:
                return _strip_sensevoice_tags(value)
        sentence_info = result.get("sentence_info")
        if isinstance(sentence_info, list):
            parts = [str(x.get("text", "")) for x in sentence_info if isinstance(x, dict)]
            return _strip_sensevoice_tags("".join(parts))
    if isinstance(result, list):
        return _strip_sensevoice_tags("".join(_extract_funasr_text(item) for item in result))
    return ""


def _funasr_cpu_asr(audio_bytes: bytes, filename: str) -> dict[str, Any]:
    source_path = _write_upload_to_temp(audio_bytes, filename)
    wav_path = _convert_to_wav_if_needed(source_path)
    model_name = os.getenv("FUNASR_MODEL", "iic/SenseVoiceSmall")
    started = time.time()
    try:
        from funasr import AutoModel  # type: ignore
        model = AutoModel(model=model_name, device="cpu", disable_update=True)
        result = model.generate(input=str(wav_path), language="zh", use_itn=True)
        raw_text = _extract_funasr_text(result)
        meta = {"engine": "funasr", "model": model_name, "device": "cpu", "elapsed_ms": round((time.time() - started) * 1000)}
    except Exception as inproc_exc:
        worker_python = PROJECT_ROOT / ".venv-asr" / "bin" / "python"
        worker = PROJECT_ROOT / "scripts" / "funasr_worker.py"
        if not worker_python.exists():
            raise RuntimeError(
                "FunASR is not installed in the service venv and project .venv-asr is not ready; "
                "the page is updated, but install/warm up FunASR before using funasr-cpu"
            ) from inproc_exc
        proc = subprocess.run(
            [str(worker_python), str(worker), str(wav_path), "--model", model_name, "--device", "cpu"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
        )
        json_lines = [line for line in proc.stdout.splitlines() if line.strip().startswith("{")]
        try:
            payload = json.loads(json_lines[-1] if json_lines else "{}")
        except Exception as exc:
            raise RuntimeError(f"FunASR worker returned non-JSON output: {proc.stdout[:300]} {proc.stderr[:300]}") from exc
        if proc.returncode != 0 or not payload.get("ok"):
            raise RuntimeError(f"FunASR worker failed: {payload.get('error_type')}: {payload.get('message')}") from inproc_exc
        raw_text = str(payload.get("text") or "")
        meta = dict(payload.get("meta") or {})
        meta["elapsed_ms"] = meta.get("elapsed_ms") or round((time.time() - started) * 1000)
    if not raw_text:
        raw_text = "（FunASR 未返回可展示文本，可能是静音或音频过短。）"
    return normalize_asr_result("funasr-cpu", raw_text, _simple_chinese_correction(raw_text), meta)


def transcribe_audio_bytes(channel: str, audio_bytes: bytes, filename: str, correct: bool = True) -> dict[str, Any]:
    if not audio_bytes:
        raise ValueError("empty audio upload")
    if len(audio_bytes) > 12 * 1024 * 1024:
        raise ValueError("audio upload too large for demo; keep it under 12MB")
    if channel == "stub-local":
        return _stub_asr(audio_bytes, filename)
    if channel == "funasr-cpu":
        result = _funasr_cpu_asr(audio_bytes, filename)
        if not correct:
            result["corrected_text"] = result["raw_text"]
            result["board_event"]["text"] = result["raw_text"]
        return result
    raise ValueError(f"unknown ASR channel: {channel}")


@app.get("/api/asr/channels")
def asr_channels() -> JSONResponse:
    return JSONResponse({"default": DEFAULT_ASR_CHANNEL, "channels": ASR_CHANNELS})


@app.post("/api/asr")
async def asr_upload(
    file: UploadFile = File(...),
    channel: str = Form(DEFAULT_ASR_CHANNEL),
    correct: bool = Form(True),
) -> JSONResponse:
    try:
        audio_bytes = await file.read()
        result = await asyncio.to_thread(transcribe_audio_bytes, channel, audio_bytes, file.filename or "audio.wav", correct)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error_type": type(exc).__name__, "message": str(exc)[:700]}) from exc
    return JSONResponse(result)


async def _connect_upstream(url: str, key: str):
    if websockets is None:
        raise RuntimeError("websockets package is not installed")
    headers = {"Authorization": f"Bearer {key}", "User-Agent": "qwen-audio-demo-realtime-proxy/0.1"}
    try:
        return await websockets.connect(url, additional_headers=headers, ping_interval=20, ping_timeout=20, max_size=8_000_000)
    except TypeError:
        return await websockets.connect(url, extra_headers=headers, ping_interval=20, ping_timeout=20, max_size=8_000_000)


def _event_text(event: dict[str, Any], field_order: tuple[str, ...] = ("delta", "transcript", "text")) -> tuple[str, str | None]:
    """Return text-like content from a Qwen Realtime event without exposing binary/audio payloads."""
    for field in field_order:
        value = event.get(field)
        if isinstance(value, str) and value:
            return value, field
    for container_key in ("part", "content", "item", "response"):
        container = event.get(container_key)
        if isinstance(container, dict):
            for field in field_order:
                value = container.get(field)
                if isinstance(value, str) and value:
                    return value, f"{container_key}.{field}"
    return "", None


def extract_realtime_transcript_events(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Qwen Realtime transcript/text events for the browser public board.

    The raw Realtime stream remains available in the debug event log, but the UI
    should not force users to read JSON. This function extracts the events called
    out in the official docs, including:
    - conversation.item.input_audio_transcription.completed -> user transcript
    - response.audio_transcript.delta/done -> assistant transcript
    - response.text.delta / response.output_text.delta -> assistant text
    - conversation.item.ambient_audio_transcription.delta/completed -> ambient text
    """
    event_type = event.get("type")
    if not isinstance(event_type, str):
        return []

    mapping: dict[str, tuple[str, str, tuple[str, ...]]] = {
        "conversation.item.input_audio_transcription.delta": ("user", "delta", ("delta", "transcript", "text")),
        "conversation.item.input_audio_transcription.completed": ("user", "final", ("transcript", "text", "delta")),
        "conversation.item.ambient_audio_transcription.delta": ("ambient", "delta", ("text", "delta", "transcript")),
        "conversation.item.ambient_audio_transcription.completed": ("ambient", "final", ("text", "transcript", "delta")),
        "response.audio_transcript.delta": ("assistant", "delta", ("delta", "transcript", "text")),
        "response.audio_transcript.done": ("assistant", "final", ("transcript", "text", "delta")),
        "response.text.delta": ("assistant", "delta", ("delta", "text", "transcript")),
        "response.text.done": ("assistant", "final", ("text", "transcript", "delta")),
        "response.output_text.delta": ("assistant", "delta", ("delta", "text", "transcript")),
        "response.output_text.done": ("assistant", "final", ("text", "transcript", "delta")),
    }
    if event_type in mapping:
        role, phase, fields = mapping[event_type]
        text, source_field = _event_text(event, fields)
        if text:
            return [
                {
                    "demo_event": "transcript.delta",
                    "role": role,
                    "phase": phase,
                    "text": text,
                    "source_type": event_type,
                    "source_field": source_field,
                    "item_id": event.get("item_id") or event.get("item", {}).get("id") if isinstance(event.get("item"), dict) else event.get("item_id"),
                    "response_id": event.get("response_id") or event.get("response", {}).get("id") if isinstance(event.get("response"), dict) else event.get("response_id"),
                }
            ]
        return []

    if event_type in {"conversation.item.created", "response.output_item.done"}:
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        role = item.get("role") or event.get("role") or "unknown"
        normalized_role = "assistant" if role in {"assistant", "ai"} else "user" if role == "user" else "unknown"
        out: list[dict[str, Any]] = []
        content = item.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("transcript") or part.get("text")
                if isinstance(text, str) and text:
                    out.append(
                        {
                            "demo_event": "transcript.delta",
                            "role": normalized_role,
                            "phase": "final",
                            "text": text,
                            "source_type": event_type,
                            "source_field": "item.content.transcript/text",
                            "item_id": item.get("id") or event.get("item_id"),
                            "response_id": event.get("response_id"),
                        }
                    )
        return out

    return []


def _redact_event_for_browser_log(event: dict[str, Any]) -> dict[str, Any]:
    """Keep debug logs readable by omitting huge base64 audio deltas."""
    if event.get("type") == "response.audio.delta" and isinstance(event.get("delta"), str):
        safe = dict(event)
        safe["delta"] = f"<audio b64 omitted, length={len(event['delta'])}>"
        return safe
    return event


@app.websocket("/ws/realtime")
async def realtime_proxy(client: WebSocket) -> None:
    await client.accept()
    key = _token_plan_key()
    upstream_url = f"{TOKEN_PLAN_REALTIME_WS}?model={REALTIME_MODEL}"
    upstream = None
    try:
        upstream = await _connect_upstream(upstream_url, key)
        await client.send_json({"demo_event": "proxy.connected", "upstream": "token-plan-api-ws-v1-realtime", "model": REALTIME_MODEL})

        async def upstream_to_client() -> None:
            async for message in upstream:
                if isinstance(message, bytes):
                    await client.send_json({"demo_event": "upstream.binary", "bytes": len(message)})
                    continue
                try:
                    event = json.loads(message)
                except Exception:
                    await client.send_text(message)
                    continue
                for transcript_event in extract_realtime_transcript_events(event):
                    await client.send_json(transcript_event)
                await client.send_json({"demo_event": "upstream.event", "event": _redact_event_for_browser_log(event)})

        async def client_to_upstream() -> None:
            while True:
                message = await client.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("text") is not None:
                    await upstream.send(message["text"])
                elif message.get("bytes") is not None:
                    await upstream.send(message["bytes"])

        done, pending = await asyncio.wait(
            {asyncio.create_task(upstream_to_client()), asyncio.create_task(client_to_upstream())},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                raise exc
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await client.send_json({"demo_event": "proxy.error", "error_type": type(exc).__name__, "message": str(exc)[:500]})
        except Exception:
            pass
    finally:
        if upstream is not None:
            await upstream.close()
        try:
            await client.close()
        except Exception:
            pass
