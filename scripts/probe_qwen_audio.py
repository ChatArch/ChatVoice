#!/usr/bin/env python3
"""Minimal sanitized probes for Token Plan audio models.

Reads OPENAI_API_KEY from the ChatEnv-derived process environment. The key must
be a Token Plan sk-sp key. Prints only sanitized status metadata; never prints
the API key or full signed audio URL.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def read_profile(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def redact_url(url: str) -> str:
    if not url:
        return ""
    return url.split("?", 1)[0] + ("?[REDACTED]" if "?" in url else "")


def load_api_key(env_file: str | None = None) -> str:
    if env_file:
        raise RuntimeError("--env-file is no longer supported; use the ChatEnv ChatVoice profile and OPENAI_API_KEY")
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("No OPENAI_API_KEY found in the ChatEnv-derived process environment")
    if not key.startswith("sk-sp"):
        raise RuntimeError("OPENAI_API_KEY must be a Token Plan sk-sp key")
    return key


def print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))


def probe_tts(args: argparse.Namespace) -> int:
    api_key = load_api_key(args.env_file)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": args.tts_model,
        "input": {
            "text": args.text,
            "voice": args.voice,
            "format": args.format,
            "sample_rate": args.sample_rate,
        },
    }
    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "qwen-audio-demo-probe/0.1",
        },
        method="POST",
    )
    started = time.time()
    result: dict[str, Any] = {
        "probe": "tts-http",
        "model": args.tts_model,
        "voice": args.voice,
        "format": args.format,
        "sample_rate": args.sample_rate,
        "text_characters": len(args.text),
        "api_key_sha256_12": hashlib.sha256(api_key.encode()).hexdigest()[:12],
    }
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            result["http_status"] = resp.status
            data = json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")[:1200]
        result.update({"http_status": e.code, "error_preview": err_body.replace(api_key, "[REDACTED]")})
        print_json(result)
        return 1
    except Exception as e:
        result.update({"error_type": type(e).__name__, "error": str(e).replace(api_key, "[REDACTED]")})
        print_json(result)
        return 1

    result["elapsed_ms"] = round((time.time() - started) * 1000)
    result["request_id"] = data.get("request_id")
    result["usage"] = data.get("usage")
    audio = (data.get("output") or {}).get("audio") or {}
    result["finish_reason"] = (data.get("output") or {}).get("finish_reason")
    result["audio_id"] = audio.get("id")
    result["audio_url_redacted"] = redact_url(audio.get("url", ""))
    result["expires_at"] = audio.get("expires_at")

    if audio.get("data"):
        raw = base64.b64decode(audio["data"])
        outfile = outdir / f"tts-{result.get('request_id') or int(time.time())}.{args.format}"
        outfile.write_bytes(raw)
        result["audio_download"] = "embedded-base64"
        result["audio_file"] = str(outfile)
        result["audio_bytes"] = len(raw)
        result["audio_sha256_12"] = hashlib.sha256(raw).hexdigest()[:12]
    elif audio.get("url"):
        try:
            with urllib.request.urlopen(audio["url"], timeout=args.timeout) as r:
                raw = r.read()
            ext = args.format if args.format in {"mp3", "wav", "pcm", "opus"} else "audio"
            outfile = outdir / f"tts-{result.get('request_id') or int(time.time())}.{ext}"
            outfile.write_bytes(raw)
            result["audio_download"] = "url"
            result["audio_file"] = str(outfile)
            result["audio_bytes"] = len(raw)
            result["audio_sha256_12"] = hashlib.sha256(raw).hexdigest()[:12]
        except Exception as e:
            result["audio_download_error"] = type(e).__name__ + ": " + str(e)
    print_json(result)
    return 0 if result.get("http_status") == 200 and (result.get("audio_bytes") or 0) > 0 else 2


def probe_realtime(args: argparse.Namespace) -> int:
    import websocket  # websocket-client

    api_key = load_api_key(args.env_file)
    url = f"wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={args.realtime_model}"
    result: dict[str, Any] = {
        "probe": "realtime-websocket-handshake",
        "model": args.realtime_model,
        "voice": args.realtime_voice,
        "api_key_sha256_12": hashlib.sha256(api_key.encode()).hexdigest()[:12],
        "events": [],
    }
    try:
        ws = websocket.create_connection(
            url,
            timeout=args.timeout,
            header=[
                f"Authorization: Bearer {api_key}",
                "User-Agent: qwen-audio-demo-probe/0.1",
            ],
            sslopt={"cert_reqs": ssl.CERT_REQUIRED},
        )
        ws.settimeout(args.timeout)
        result["connected"] = True
        # read server-created event if sent immediately
        deadline = time.time() + args.timeout
        got_created = False
        while time.time() < deadline:
            try:
                msg = ws.recv()
            except Exception:
                break
            event = json.loads(msg)
            t = event.get("type")
            result["events"].append({"type": t, "keys": sorted(event.keys()), "error": event.get("error")})
            if t == "session.created":
                got_created = True
                break
            if t == "error":
                break
        update = {
            "event_id": f"event_probe_{int(time.time()*1000)}",
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "voice": args.realtime_voice,
                "input_audio_format": "pcm",
                "output_audio_format": "pcm",
                "turn_detection": {"type": "server_vad", "threshold": 0.5, "silence_duration_ms": 800},
            },
        }
        ws.send(json.dumps(update, ensure_ascii=False))
        deadline = time.time() + args.timeout
        while time.time() < deadline and len(result["events"]) < args.max_events:
            try:
                msg = ws.recv()
            except Exception as e:
                result["recv_stop"] = type(e).__name__
                break
            try:
                event = json.loads(msg)
            except json.JSONDecodeError:
                result["events"].append({"type": "non-json", "bytes": len(msg)})
                continue
            item = {"type": event.get("type"), "keys": sorted(event.keys())}
            if event.get("type") == "error":
                item["error"] = event.get("error")
            if event.get("type") in {"session.updated", "session.created"}:
                sess = event.get("session") or {}
                item["session_keys"] = sorted(sess.keys()) if isinstance(sess, dict) else []
            result["events"].append(item)
            if event.get("type") in {"session.updated", "error"} and len(result["events"]) >= 2:
                break
        try:
            ws.close()
        except Exception:
            pass
    except Exception as e:
        result.update({"connected": False, "error_type": type(e).__name__, "error": str(e).replace(api_key, "[REDACTED]")})
        print_json(result)
        return 1
    print_json(result)
    return 0 if result.get("connected") and any(e.get("type") in {"session.created", "session.updated"} for e in result["events"]) else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["tts", "realtime"])
    ap.add_argument("--env-file", default=None, help="Deprecated; use the ChatEnv ChatVoice profile and OPENAI_API_KEY")
    ap.add_argument("--timeout", type=float, default=20)
    ap.add_argument("--outdir", default="playground/probe-output")
    ap.add_argument("--text", default="你好，这是千问语音合成的最小探针。")
    ap.add_argument("--tts-model", default="qwen-audio-3.0-tts-plus")
    ap.add_argument("--voice", default="longanlingxin")
    ap.add_argument("--format", default="mp3")
    ap.add_argument("--sample-rate", type=int, default=24000)
    ap.add_argument("--realtime-model", default="qwen-audio-3.0-realtime-plus")
    ap.add_argument("--realtime-voice", default="longanqian")
    ap.add_argument("--max-events", type=int, default=6)
    args = ap.parse_args()
    if args.mode == "tts":
        return probe_tts(args)
    return probe_realtime(args)


if __name__ == "__main__":
    sys.exit(main())
