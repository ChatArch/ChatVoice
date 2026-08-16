#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import difflib
import io
import json
import re
import urllib.request
import wave
from urllib.parse import urlparse

import websockets


SOURCE_TEXT = (
    "今天我们确认三个事项。第一，实时录音需要自动分片，并连续显示识别文字。"
    "第二，转写结果要尽量保持原意，不遗漏关键内容。"
    "第三，会议结束后生成摘要和行动项。"
)


def normalized(text: str) -> str:
    return "".join(char for char in text if char.isalnum()).lower()


def post_json(url: str, payload: dict[str, object], timeout: int = 120) -> tuple[bytes, dict[str, str]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), dict(response.headers.items())


async def stream_asr(base_url: str, wav_bytes: bytes) -> list[str]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        sample_rate = wav.getframerate()
        pcm = wav.readframes(wav.getnframes())

    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_url = f"{scheme}://{parsed.netloc}/ws/asr/stream"
    frame_bytes = sample_rate * 2
    revisions: list[str] = []
    async with websockets.connect(ws_url, open_timeout=15, max_size=2_000_000) as socket:
        ready = json.loads(await asyncio.wait_for(socket.recv(), 15))
        assert ready.get("demo_event") == "asr.stream.ready", ready
        await socket.send(json.dumps({
            "type": "asr.stream.start",
            "channel": "funasr-gpu",
            "sample_rate": sample_rate,
            "chunk_seconds": 3,
        }))
        started = json.loads(await asyncio.wait_for(socket.recv(), 15))
        assert started.get("demo_event") == "asr.stream.started", started
        for offset in range(0, len(pcm), frame_bytes):
            await socket.send(pcm[offset:offset + frame_bytes])
        await socket.send(json.dumps({"type": "asr.stream.finish"}))
        while True:
            event = json.loads(await asyncio.wait_for(socket.recv(), 180))
            if event.get("demo_event") == "asr.stream.result":
                text = str((event.get("board_event") or {}).get("text") or "").strip()
                if text:
                    revisions.append(text)
            if event.get("demo_event") == "asr.stream.error":
                raise RuntimeError(event.get("message") or "ASR stream error")
            if event.get("demo_event") == "asr.stream.done":
                break
    return revisions


async def main() -> int:
    parser = argparse.ArgumentParser(description="Qwen TTS -> chunked GPU ASR -> Qwen summary end-to-end check")
    parser.add_argument("--base-url", default="http://127.0.0.1:18087")
    parser.add_argument("--min-similarity", type=float, default=0.85)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    wav_bytes, tts_headers = post_json(f"{base_url}/api/tts", {
        "text": SOURCE_TEXT,
        "voice": "longanlingxin",
        "format": "wav",
    })
    revisions = await stream_asr(base_url, wav_bytes)
    merged = revisions[-1] if revisions else ""
    segments = [part.strip() for part in re.findall(r"[^。！？!?]+[。！？!?]?", merged) if normalized(part)]
    similarity = difflib.SequenceMatcher(None, normalized(SOURCE_TEXT), normalized(merged)).ratio()

    summary_bytes, _ = post_json(f"{base_url}/api/meeting-notes/polish", {
        "transcript": merged,
        "instruction": "请输出简短中文会议摘要，并列出行动项。只根据输入文本，不编造。",
    })
    summary = json.loads(summary_bytes.decode("utf-8"))
    summary_content = str(summary.get("content") or "")
    lower_headers = {key.lower(): value for key, value in tts_headers.items()}
    checks = {
        "tts_audio_bytes": len(wav_bytes),
        "tts_elapsed_ms": lower_headers.get("x-elapsed-ms"),
        "segment_count": len(segments),
        "segments": segments,
        "revision_count": len(revisions),
        "revision_updates_are_cumulative": len(set(revisions)) >= 2,
        "merged_transcript": merged,
        "similarity": round(similarity, 4),
        "summary_model": summary.get("model"),
        "summary_chars": len(summary_content),
        "summary_mentions_actions": "行动" in summary_content,
        "ok": bool(segments) and len(revisions) >= 2 and similarity >= args.min_similarity and bool(summary_content),
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
