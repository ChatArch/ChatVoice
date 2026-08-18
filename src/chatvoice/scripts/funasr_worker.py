#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


def strip_sensevoice_tags(text: str) -> str:
    return " ".join(re.sub(r"<\|[^|>]+\|>", "", text or "").split()).strip()


def extract_text(result: Any) -> str:
    if isinstance(result, str):
        return strip_sensevoice_tags(result)
    if isinstance(result, dict):
        value = result.get("text")
        if isinstance(value, str) and value:
            return strip_sensevoice_tags(value)
        sentence_info = result.get("sentence_info")
        if isinstance(sentence_info, list):
            return strip_sensevoice_tags("".join(str(item.get("text", "")) for item in sentence_info if isinstance(item, dict)))
    if isinstance(result, list):
        return strip_sensevoice_tags("".join(extract_text(item) for item in result))
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio_path")
    ap.add_argument("--model", default="iic/SenseVoiceSmall")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    audio_path = Path(args.audio_path)
    project_root = Path(__file__).resolve().parents[1]
    cache_root = project_root / "playground" / "model-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    import os
    os.environ.setdefault("MODELSCOPE_CACHE", str(cache_root / "modelscope"))
    os.environ.setdefault("HF_HOME", str(cache_root / "huggingface"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_root / "transformers"))
    started = time.time()
    try:
        from funasr import AutoModel  # type: ignore
        model = AutoModel(model=args.model, device=args.device, disable_update=True)
        result = model.generate(input=str(audio_path), language="zh", use_itn=True)
        text = extract_text(result)
        payload = {
            "ok": True,
            "text": text,
            "raw_result_type": type(result).__name__,
            "meta": {
                "engine": "funasr-worker",
                "model": args.model,
                "device": args.device,
                "elapsed_ms": round((time.time() - started) * 1000),
            },
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "error_type": type(exc).__name__,
            "message": str(exc)[:1000],
            "meta": {"engine": "funasr-worker", "model": args.model, "device": args.device},
        }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
