#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import math
import os
import struct
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(PROJECT_ROOT))

import app.main as main  # noqa: E402


def make_test_wav(duration_seconds: float = 0.1, sample_rate: int = 16000) -> bytes:
    path = PROJECT_ROOT / "playground" / "asr-gpu-contract-tone.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(int(duration_seconds * sample_rate)):
        value = int(160 * math.sin(2 * math.pi * 440 * (i / sample_rate)))
        frames.append(struct.pack("<h", value))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))
    return path.read_bytes()

checks: dict[str, object] = {}
checks["default_is_funasr_gpu"] = main.DEFAULT_ASR_CHANNEL == "funasr-gpu"
checks["channel_funasr_gpu_exists"] = "funasr-gpu" in main.ASR_CHANNELS
checks["channel_funasr_gpu_cuda"] = main.ASR_CHANNELS.get("funasr-gpu", {}).get("device") in {"cuda", "cuda:0"}
checks["channel_funasr_cpu_not_default"] = "funasr-cpu" in main.ASR_CHANNELS and main.DEFAULT_ASR_CHANNEL != "funasr-cpu"
checks["stream_route_exists"] = any(getattr(route, "path", None) == "/ws/asr/stream" for route in main.app.routes)
checks["pcm16_wav_helper_exists"] = callable(getattr(main, "pcm16_to_wav_bytes", None))
checks["chunk_session_class_exists"] = hasattr(main, "AsrStreamSession")
checks["normalizer_source_type_gpu"] = main.normalize_asr_result("funasr-gpu", "我想嗯测试", "我想测试。", {"engine": "contract"})["board_event"]["source_type"] == "asr.funasr-gpu"
# The stub path must stay available so public smoke can run even if GPU model is warming/downloading.
wav = make_test_wav()
stub = main.transcribe_audio_bytes("stub-local", wav, "asr-gpu-contract-tone.wav", True)
checks["stub_still_available"] = bool(stub.get("board_event") and base64.b64encode(wav))
original_profile = main._read_profile
original_env = os.environ.copy()
try:
    for key in ("QWEN_MEETING_NOTES_MODEL", "QWEN_CODING_PLAN_MODEL"):
        os.environ.pop(key, None)
    main._read_profile = lambda: {"OPENAI_API_MODEL": "qwen3.7-plus"}
    checks["meeting_notes_model_prefers_profile"] = main._meeting_notes_model() == "qwen3.7-plus"
finally:
    main._read_profile = original_profile
    os.environ.clear()
    os.environ.update(original_env)
checks["ok"] = all(bool(v) for k, v in checks.items() if k != "ok")
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if checks["ok"] else 1)
