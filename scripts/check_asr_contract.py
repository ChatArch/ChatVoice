#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import math
import struct
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from chatvoice.web.legacy_app import (  # noqa: E402
    ASR_CHANNELS,
    _extract_funasr_text,
    normalize_asr_result,
    transcribe_audio_bytes,
)


def make_test_wav(duration_seconds: float = 0.25, sample_rate: int = 16000) -> bytes:
    path = PROJECT_ROOT / "playground" / "asr-contract-silence.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(int(duration_seconds * sample_rate)):
        # very quiet tone, not speech; the contract test validates shape and error handling.
        value = int(200 * math.sin(2 * math.pi * 440 * (i / sample_rate)))
        frames.append(struct.pack("<h", value))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))
    return path.read_bytes()


def main() -> int:
    checks: dict[str, object] = {}
    checks["channels_have_funasr_gpu"] = "funasr-gpu" in ASR_CHANNELS
    checks["default_channel_is_gpu"] = ASR_CHANNELS.get("funasr-gpu", {}).get("device") in {"cuda", "cuda:0"}
    normalized = normalize_asr_result(
        channel="funasr-gpu",
        raw_text="我想嗯测试这个",
        corrected_text="我想测试这个。",
        meta={"engine": "contract"},
    )
    checks["normalized_has_raw"] = normalized["raw_text"] == "我想嗯测试这个"
    checks["normalized_has_corrected"] = normalized["corrected_text"] == "我想测试这个。"
    checks["normalized_board_event"] = normalized["board_event"] == {
        "demo_event": "transcript.delta",
        "role": "user",
        "phase": "final",
        "text": "我想测试这个。",
        "raw_text": "我想嗯测试这个",
        "source_type": "asr.funasr-gpu",
    }
    checks["sensevoice_tags_stripped"] = _extract_funasr_text([
        {"text": "<|zh|><|NEUTRAL|><|Speech|><|withitn|>你好，这是FunASR GPU识别测试。"}
    ]) == "你好，这是FunASR GPU识别测试。"
    wav_bytes = make_test_wav()
    try:
        result = transcribe_audio_bytes(
            channel="stub-local",
            audio_bytes=wav_bytes,
            filename="asr-contract-silence.wav",
            correct=True,
        )
        checks["stub_transcribe_shape"] = bool(result.get("board_event") and "raw_text" in result and "corrected_text" in result)
        checks["stub_audio_base64_len"] = len(base64.b64encode(wav_bytes).decode()) > 100
    except Exception as exc:
        checks["stub_transcribe_shape"] = False
        checks["stub_error"] = type(exc).__name__ + ": " + str(exc)
    checks["ok"] = all(v for k, v in checks.items() if k not in {"stub_error"})
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
