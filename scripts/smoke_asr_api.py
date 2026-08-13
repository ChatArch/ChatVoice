#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import http.client
import json
import math
import socket
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def wait_port(port: int, timeout: float = 20) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"port {port} not ready")


def make_wav(path: Path, duration: float = 0.25, sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(int(duration * sample_rate)):
        value = int(200 * math.sin(2 * math.pi * 440 * (i / sample_rate)))
        frames.append(struct.pack("<h", value))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))


def make_pcm(duration: float = 0.08, sample_rate: int = 16000) -> bytes:
    frames = bytearray()
    for i in range(int(duration * sample_rate)):
        value = int(120 * math.sin(2 * math.pi * 440 * (i / sample_rate)))
        frames += struct.pack("<h", value)
    return bytes(frames)


def http_json(port: int, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    data = resp.read()
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception:
        payload = {"raw": data.decode("utf-8", "ignore")[:500]}
    return resp.status, payload


def multipart(field_name: str, filename: str, content: bytes, extra: dict[str, str]) -> tuple[bytes, str]:
    boundary = "----qwenDemoAsrBoundary"
    parts: list[bytes] = []
    for k, v in extra.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field_name}\"; filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n".encode()
        + content
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


def smoke_asr_stream_contract() -> dict:
    import app.main as main

    client = TestClient(main.app)
    pcm = make_pcm()
    with client.websocket_connect("/ws/asr/stream") as ws:
        ready = ws.receive_json()
        ws.send_json({"type": "asr.stream.start", "channel": "stub-local", "sample_rate": 16000, "chunk_seconds": 1})
        started = ws.receive_json()
        ws.send_json({"type": "asr.stream.append", "audio": base64.b64encode(pcm).decode()})
        ws.send_json({"type": "asr.stream.commit"})
        events = []
        for _ in range(4):
            ev = ws.receive_json()
            events.append(ev)
            if ev.get("demo_event") == "asr.stream.done":
                break
    result_event = next((e for e in events if e.get("demo_event") == "asr.stream.result"), {})
    return {
        "ready_default_channel": ready.get("channel"),
        "started_channel": started.get("channel"),
        "has_stream_result": bool(result_event),
        "result_source_type": ((result_event.get("board_event") or {}).get("source_type")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18097)
    args = ap.parse_args()
    wav_path = PROJECT_ROOT / "playground" / "asr-temp" / "smoke-stub.wav"
    make_wav(wav_path)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_port(args.port)
        status_status, status = http_json(args.port, "GET", "/api/status")
        status_channels, channels = http_json(args.port, "GET", "/api/asr/channels")
        body, boundary = multipart("file", "smoke-stub.wav", wav_path.read_bytes(), {"channel": "stub-local", "correct": "true"})
        status_asr, asr = http_json(
            args.port,
            "POST",
            "/api/asr",
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))},
        )
        stream = smoke_asr_stream_contract()
        checks = {
            "status_status": status_status,
            "channels_status": status_channels,
            "asr_status": status_asr,
            "default_is_funasr_gpu": status.get("asr_default_channel") == "funasr-gpu",
            "has_funasr_gpu": "funasr-gpu" in (channels.get("channels") or {}),
            "has_funasr_cpu": "funasr-cpu" in (channels.get("channels") or {}),
            "stub_channel": asr.get("channel") == "stub-local",
            "has_board_event": isinstance(asr.get("board_event"), dict) and asr["board_event"].get("demo_event") == "transcript.delta",
            "has_raw_and_corrected": bool(asr.get("raw_text") and asr.get("corrected_text")),
            "stream_ready_default_gpu": stream.get("ready_default_channel") == "funasr-gpu",
            "stream_stub_result": stream.get("has_stream_result") and stream.get("result_source_type") == "asr.stream.stub-local",
        }
        checks["ok"] = all(v for k, v in checks.items() if k not in {"status_status", "channels_status", "asr_status"}) and status_status == status_channels == status_asr == 200
        print(json.dumps({"ok": checks["ok"], "checks": checks, "stream": stream, "asr": asr}, ensure_ascii=False, indent=2))
        return 0 if checks["ok"] else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
