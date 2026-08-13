#!/usr/bin/env python3
"""Token Plan TTS probe using the official DashScope websocket path.

Reads OPENAI_API_KEY / DASHSCOPE_API_KEY from the server environment, or from
QWEN_TOKEN_PLAN_ENV_FILE. Prints only sanitized metadata.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path


def read_env_file(path: str | None) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path:
        return data
    p = Path(path).expanduser()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip("\"").strip("'")
    return data


def load_key() -> str:
    env = read_env_file(os.getenv("QWEN_TOKEN_PLAN_ENV_FILE"))
    for key_name in ("OPENAI_API_KEY", "DASHSCOPE_API_KEY"):
        if os.getenv(key_name):
            env[key_name] = os.environ[key_name]
    key = env.get("OPENAI_API_KEY") or env.get("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError("No OPENAI_API_KEY/DASHSCOPE_API_KEY found")
    return key


def main() -> int:
    outdir = Path("playground/probe-output")
    outdir.mkdir(parents=True, exist_ok=True)
    key = load_key()
    result = {
        "probe": "token-plan-tts-dashscope-ws-sdk",
        "model": "qwen-audio-3.0-tts-plus",
        "voice": "longanlingxin",
        "api_key_sha256_12": hashlib.sha256(key.encode()).hexdigest()[:12],
    }
    try:
        import dashscope
        from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer

        dashscope.api_key = key
        dashscope.base_websocket_api_url = "wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
        started = time.time()
        synthesizer = SpeechSynthesizer(
            model="qwen-audio-3.0-tts-plus",
            voice="longanlingxin",
            format=AudioFormat.MP3_22050HZ_MONO_256KBPS,
        )
        audio = synthesizer.call("你好，这是 Token Plan 千问语音合成的最小探针。")
        result["elapsed_ms"] = round((time.time() - started) * 1000)
        result["request_id"] = getattr(synthesizer, "get_last_request_id", lambda: None)()
        result["first_package_delay_ms"] = getattr(synthesizer, "get_first_package_delay", lambda: None)()
        if audio:
            out = outdir / f"token-plan-tts-{int(time.time())}.mp3"
            out.write_bytes(audio)
            result["audio_file"] = str(out)
            result["audio_bytes"] = len(audio)
            result["audio_sha256_12"] = hashlib.sha256(audio).hexdigest()[:12]
        else:
            result["audio_bytes"] = 0
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc).replace(key, "[REDACTED]")[:1600]
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("audio_bytes", 0) > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
