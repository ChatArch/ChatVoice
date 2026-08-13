#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn

from app.main import app


def http_get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def http_post_tts(url: str) -> dict:
    payload = json.dumps({"text": "你好，这是网页 Demo 的自动 smoke。", "voice": "longanlingxin", "format": "mp3"}, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as response:
        body = response.read()
        return {
            "status": response.status,
            "content_type": response.headers.get("content-type"),
            "bytes": len(body),
            "request_id": response.headers.get("x-qwen-request-id"),
            "sha256_12": response.headers.get("x-audio-sha256-12"),
            "elapsed_ms": response.headers.get("x-elapsed-ms"),
        }


async def ws_probe(url: str) -> dict:
    import websockets
    result = {"events": []}
    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
        await ws.send(json.dumps({"event_id": "smoke_session_update", "type": "session.update", "session": {"modalities": ["text", "audio"], "voice": "longanqian", "input_audio_format": "pcm", "output_audio_format": "pcm", "turn_detection": {"type": "server_vad", "threshold": 0.5, "silence_duration_ms": 800}}}, ensure_ascii=False))
        deadline = time.time() + 10
        while time.time() < deadline and len(result["events"]) < 6:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3)
            except asyncio.TimeoutError:
                result["events"].append({"recv_stop": "timeout"})
                break
            try:
                event = json.loads(msg)
            except Exception:
                result["events"].append({"type": "non-json", "length": len(msg)})
                continue
            result["events"].append({"type": event.get("type") or event.get("demo_event"), "keys": sorted(event.keys())})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18087)
    args = parser.parse_args()

    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://{args.host}:{args.port}"
    result = {"base_url": base}
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                result["status"] = http_get_json(base + "/api/status")
                break
            except Exception:
                time.sleep(0.25)
        else:
            result["error"] = "server did not become ready"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        result["tts"] = http_post_tts(base + "/api/tts")
        result["realtime_ws"] = asyncio.run(ws_probe(f"ws://{args.host}:{args.port}/ws/realtime"))
        ok = result["status"].get("models_ok") and result["tts"].get("bytes", 0) > 1000 and any(e.get("type") in {"proxy.connected", "session.created", "session.updated"} for e in result["realtime_ws"].get("events", []))
        result["ok"] = bool(ok)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if ok else 2
    finally:
        server.should_exit = True
        thread.join(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
