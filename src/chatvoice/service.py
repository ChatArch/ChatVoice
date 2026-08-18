"""Service planning and startup helpers for ChatVoice."""

from __future__ import annotations

from typing import Any

from chatvoice.asr import get_asr_channels
from chatvoice.paths import database_settings, ensure_runtime_dirs, state_paths


def render_service_plan(*, host: str = "127.0.0.1", port: int = 18087, workers: int = 1) -> dict[str, Any]:
    """Return a sanitized plan for starting the packaged Speakr web service."""

    paths = state_paths()
    database = database_settings()
    return {
        "command": ["chatvoice", "serve", "app", "--host", host, "--port", str(port)],
        "host": host,
        "port": int(port),
        "workers": int(workers),
        "paths": paths.as_dict(),
        "database": database,
        "asr": get_asr_channels(),
        "web_app": "chatvoice.web.server:create_app",
        "production_boundary": {
            "gpu_runtime": "external-api-preferred",
            "secrets": "read from environment or ChatEnv; never pass API keys in argv",
            "sqlite_limit": "keep one service process for SQLite WAL; migrate storage before multi-worker/high-concurrency deployment",
        },
    }


def serve_app(*, host: str = "127.0.0.1", port: int = 18087, reload: bool = False, workers: int = 1) -> None:
    """Start the packaged Speakr FastAPI application with Uvicorn."""

    ensure_runtime_dirs()
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - exercised in packaging smoke.
        raise RuntimeError("Install ChatVoice with the web extra first: python -m pip install 'ChatVoice[web]'.") from exc
    uvicorn.run(
        "chatvoice.web.server:create_app",
        factory=True,
        host=host,
        port=int(port),
        reload=reload,
        workers=max(1, int(workers)),
    )


__all__ = ["render_service_plan", "serve_app"]
