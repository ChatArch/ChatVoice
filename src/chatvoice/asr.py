"""ASR provider configuration helpers for ChatVoice."""

from __future__ import annotations

import os
from urllib.parse import urlparse


def _bool_env(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def configured_api_endpoint() -> str:
    """Return the configured ASR API endpoint without printing credentials."""

    return os.getenv("CHATVOICE_ASR_API_URL", os.getenv("ASR_API_URL", "")).strip()


def default_asr_channel() -> str:
    """Resolve the default ASR provider channel."""

    explicit = os.getenv("CHATVOICE_ASR_CHANNEL", os.getenv("DEFAULT_ASR_CHANNEL", "")).strip()
    if explicit:
        return explicit
    return "api-server" if configured_api_endpoint() else "stub-local"


def get_asr_channels() -> dict[str, object]:
    """Return a sanitized ASR channel map.

    ``api-server`` is the preferred production shape: ChatVoice calls an API
    endpoint that may be a managed cloud ASR service or a self-hosted GPU ASR
    server. API keys are represented only as configured/not-configured booleans.
    """

    endpoint = configured_api_endpoint()
    host = urlparse(endpoint).netloc if endpoint else ""
    return {
        "default": default_asr_channel(),
        "channels": {
            "api-server": {
                "label": "ASR API Server / managed API",
                "engine": "api",
                "status": "ready" if endpoint else "needs-config",
                "url_configured": bool(endpoint),
                "endpoint_host": host or None,
                "api_key_configured": _bool_env("CHATVOICE_ASR_API_KEY") or _bool_env("ASR_API_KEY"),
                "notes": "Recommended production mode. The API endpoint can front a cloud provider or a self-hosted GPU ASR server.",
            },
            "stub-local": {
                "label": "Local contract smoke channel",
                "engine": "stub",
                "status": "ready",
                "device": "cpu",
                "notes": "Starts without GPU or cloud credentials; verifies upload, storage, UI, and service wiring only.",
            },
            "funasr-gpu": {
                "label": "FunASR GPU local worker",
                "engine": "funasr",
                "status": "optional-local-worker",
                "device": os.getenv("FUNASR_GPU_DEVICE", "cuda:0"),
                "notes": "Optional compatibility mode. Prefer api-server for flexible GPU deployment.",
            },
            "funasr-cpu": {
                "label": "FunASR CPU fallback",
                "engine": "funasr",
                "status": "optional-debug",
                "device": "cpu",
                "notes": "Debug fallback only; not recommended for production transcription quality or latency.",
            },
        },
    }


__all__ = ["configured_api_endpoint", "default_asr_channel", "get_asr_channels"]
