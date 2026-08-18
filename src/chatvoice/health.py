"""HTTP health checks for ChatVoice services."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def get_status(base_url: str = "http://127.0.0.1:18087", *, timeout: float = 5.0) -> dict[str, Any]:
    """Read ``/api/status`` from a ChatVoice/Speakr service."""

    url = base_url.rstrip("/") + "/api/status"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(1_000_000)
            payload = json.loads(body.decode("utf-8"))
            return {"ok": True, "url": url, "status_code": response.status, "payload": payload}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "url": url, "status_code": exc.code, "error": exc.reason}
    except Exception as exc:
        return {"ok": False, "url": url, "error_type": type(exc).__name__, "error": str(exc)}


__all__ = ["get_status"]
