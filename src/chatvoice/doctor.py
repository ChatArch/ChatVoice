"""Local diagnostic summaries for ChatVoice."""

from __future__ import annotations

import shutil
from typing import Any

from chatvoice.asr import get_asr_channels
from chatvoice.paths import database_settings, state_paths


def run_doctor() -> dict[str, Any]:
    """Return a non-secret local readiness summary."""

    paths = state_paths()
    database = database_settings()
    asr = get_asr_channels()
    return {
        "ok": database["supported_by_packaged_web_app"],
        "paths": paths.as_dict(),
        "database": database,
        "asr": asr,
        "commands": {
            "ffmpeg": bool(shutil.which("ffmpeg")),
        },
        "warnings": [
            "SQLite WAL is a single-node default; use one service worker or migrate storage before high concurrency."
        ] if database["backend"] == "sqlite" else [
            "External DB URL is configured, but v0.1.4 packaged web storage still supports SQLite only."
        ],
    }


__all__ = ["run_doctor"]
