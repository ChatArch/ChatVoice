"""FastAPI app factory for the packaged ChatVoice/Speakr service."""

from __future__ import annotations

import os
from pathlib import Path

from chatvoice.paths import ensure_runtime_dirs


def create_app():
    """Create the packaged Speakr FastAPI app.

    The legacy application computes several paths at import time, so the factory
    resolves ChatArch runtime paths and safe defaults before importing it.
    """

    paths = ensure_runtime_dirs()
    static_dir = Path(__file__).resolve().parent / "static"
    os.environ.setdefault("CHATVOICE_RUNTIME_ROOT", str(paths.root))
    os.environ.setdefault("CHATVOICE_STATIC_DIR", str(static_dir))
    os.environ.setdefault("MEETING_DB_PATH", str(paths.database_path))
    os.environ.setdefault("MODELSCOPE_CACHE", str(paths.model_cache_dir / "modelscope"))
    os.environ.setdefault("HF_HOME", str(paths.model_cache_dir / "huggingface"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(paths.model_cache_dir / "transformers"))
    from chatvoice.web.legacy_app import app

    return app


__all__ = ["create_app"]
