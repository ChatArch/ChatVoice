from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import io
import json
import logging
import math
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import wave
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import dashscope
from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

try:
    import websockets
except Exception:  # pragma: no cover
    websockets = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "app" / "static"
PROFILE_ENV_FILE = os.getenv("QWEN_TOKEN_PLAN_ENV_FILE", "").strip()
PROFILE_PATH = Path(PROFILE_ENV_FILE).expanduser() if PROFILE_ENV_FILE else None
TOKEN_PLAN_TTS_WS = "wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
TOKEN_PLAN_REALTIME_WS = "wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime"
DASHSCOPE_HTTP_API_BASE = os.getenv("DASHSCOPE_HTTP_API_BASE", "https://dashscope.aliyuncs.com/api/v1").rstrip("/")
REALTIME_MODEL = "qwen-audio-3.0-realtime-plus"
TTS_MODEL = "qwen-audio-3.0-tts-plus"
DEFAULT_VOICE = "longanlingxin"
FUNASR_MODEL = os.getenv("FUNASR_MODEL", "iic/SenseVoiceSmall")
FUNASR_GPU_DEVICE = os.getenv("FUNASR_GPU_DEVICE", "cuda:0")
DEFAULT_ASR_CHANNEL = os.getenv("DEFAULT_ASR_CHANNEL", "funasr-gpu")
MEETING_NOTES_MODEL = os.getenv("QWEN_MEETING_NOTES_MODEL", os.getenv("QWEN_CODING_PLAN_MODEL", "qwen3.7-plus"))
MEETING_TITLE_MODEL = os.getenv("QWEN_MEETING_TITLE_MODEL", "qwen3.6-flash")
ALLOWED_ASR_STREAM_SAMPLE_RATES = {8000, 16000, 24000, 48000}
MIN_ASR_STREAM_CHUNK_SECONDS = 0.5
MAX_ASR_STREAM_CHUNK_SECONDS = 10.0
MAX_ASR_STREAM_FRAME_BYTES = 256 * 1024
MAX_ASR_STREAM_JSON_FRAME_BYTES = 384 * 1024
MAX_ASR_STREAM_BUFFER_SECONDS = 20.0
ASR_STREAM_CONTEXT_SECONDS = 45.0
GUEST_ASR_STREAM_SECONDS = 10 * 60
ACCOUNT_ASR_STREAM_SECONDS = 2 * 60 * 60
MAX_ASR_STREAM_CHUNKS_PER_RECEIVE = 2
MAX_ASR_STREAM_CHUNKS_PER_CONNECTION = 20_000
ASR_CHANNELS: dict[str, dict[str, Any]] = {
    "funasr-gpu": {
        "label": "FunASR GPU（CUDA PyTorch + SenseVoiceSmall）",
        "engine": "funasr",
        "device": FUNASR_GPU_DEVICE,
        "status": "lazy-load",
        "notes": "默认真实 ASR 通道；通过 .venv-asr-gpu worker 使用 CUDA PyTorch/FunASR。",
    },
    "funasr-cpu": {
        "label": "FunASR CPU（fallback / debug）",
        "engine": "funasr",
        "device": "cpu",
        "status": "fallback",
        "notes": "仅作为 GPU 不可用时的显式 fallback，不再是默认通道。",
    },
    "stub-local": {
        "label": "本地合同通道（无模型，用于体验/回归）",
        "engine": "stub",
        "device": "cpu",
        "status": "ready",
        "notes": "用于打通上传/录音/公网 smoke；不代表识别质量。",
    },
}

app = FastAPI(title="Qwen Token Plan Audio + GPU ASR Demo", version="0.3.0")
logger = logging.getLogger("qwen_audio_demo")
_FUNASR_MODELS: dict[tuple[str, str], Any] = {}
_FUNASR_MODEL_LOCKS: dict[tuple[str, str], threading.Lock] = {}
_FUNASR_CACHE_LOCK = threading.Lock()
MEETING_DB_PATH = Path(os.getenv("MEETING_DB_PATH", str(PROJECT_ROOT / "playground" / "meetings.sqlite3"))).expanduser()
_MEETING_DB_LOCK = threading.Lock()
AUTH_COOKIE_NAME = "meeting_session"
AUTH_SESSION_DAYS = 30
PASSWORD_ITERATIONS = 310_000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost", "http://127.0.0.1:18087", "http://localhost:18087"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=800)
    voice: str = Field(DEFAULT_VOICE, min_length=1, max_length=80)
    format: str = Field("mp3", pattern="^(mp3|wav)$")


class VoiceCloneRequest(BaseModel):
    audio_url: str = Field(..., min_length=8, max_length=2000)
    prefix: str = Field("voicenote", min_length=2, max_length=9, pattern="^[a-z0-9]+$")
    target_model: str = Field(TTS_MODEL, min_length=1, max_length=80)
    language_hints: list[str] = Field(default_factory=lambda: ["zh"])
    max_prompt_audio_length: float | None = Field(default=30.0, ge=1.0, le=180.0)


class MeetingNotesRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=20000)
    instruction: str = Field("输出中文会议纪要：先给实时摘要，再给润色修复后的逐段记录、待办、风险和未决问题。", max_length=1000)
    model: str | None = Field(default=None, max_length=120)


class MeetingTitleRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=4000)
    model: str | None = Field(default=None, max_length=120)


class StoredTranscriptSegment(BaseModel):
    speaker: str = Field("说话人 1", max_length=80)
    time: str = Field("00:00", max_length=20)
    text: str = Field(..., min_length=1, max_length=5000)


class MeetingRecordInput(BaseModel):
    title: str = Field("新录音", max_length=120)
    created_at: str = Field(..., min_length=1, max_length=64)
    updated_at: str = Field(..., min_length=1, max_length=64)
    duration_seconds: int = Field(0, ge=0, le=24 * 60 * 60)
    transcript_segments: list[StoredTranscriptSegment] = Field(default_factory=list, max_length=500)
    summary_title: str = Field("", max_length=500)
    summary_content: str = Field("", max_length=20000)


class StoredConversationMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    text: str = Field(..., min_length=1, max_length=5000)


class ConversationRecordInput(BaseModel):
    title: str = Field("新对话", max_length=120)
    model: str = Field(REALTIME_MODEL, min_length=1, max_length=120)
    voice: str = Field(DEFAULT_VOICE, min_length=1, max_length=80)
    created_at: str = Field(..., min_length=1, max_length=64)
    updated_at: str = Field(..., min_length=1, max_length=64)
    messages: list[StoredConversationMessage] = Field(default_factory=list, max_length=200)


class AccountCredentials(BaseModel):
    account: str = Field(..., min_length=3, max_length=80)
    password: str = Field(..., min_length=8, max_length=128)


def _read_profile() -> dict[str, str]:
    data: dict[str, str] = {}
    if PROFILE_PATH and PROFILE_PATH.exists():
        for raw in PROFILE_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key] = value.strip().strip('"').strip("'")
    # Allow explicit env override for a temporary shell session, but never expose it.
    for key in ("OPENAI_API_KEY", "OPENAI_API_BASE", "DASHSCOPE_API_KEY", "DASHSCOPE_VOICE_API_KEY"):
        if os.getenv(key):
            data[key] = os.environ[key]
    return data


def _token_plan_key() -> str:
    profile = _read_profile()
    key = profile.get("OPENAI_API_KEY") or profile.get("DASHSCOPE_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="Missing Token Plan API key. Set OPENAI_API_KEY or DASHSCOPE_API_KEY on the server.")
    return key


def _token_plan_base() -> str:
    profile = _read_profile()
    return profile.get("OPENAI_API_BASE", "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1").rstrip("/")


def _voice_cloning_key() -> str:
    profile = _read_profile()
    key = profile.get("DASHSCOPE_VOICE_API_KEY") or profile.get("DASHSCOPE_API_KEY")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Voice cloning is not configured. Set DASHSCOPE_VOICE_API_KEY on the server.",
        )
    return key


def _meeting_notes_model(req_model: str | None = None) -> str:
    if req_model:
        return req_model
    profile = _read_profile()
    return (
        os.getenv("QWEN_MEETING_NOTES_MODEL")
        or os.getenv("QWEN_CODING_PLAN_MODEL")
        or profile.get("OPENAI_API_MODEL")
        or MEETING_NOTES_MODEL
    )


def _meeting_title_model(req_model: str | None = None) -> str:
    return req_model or os.getenv("QWEN_MEETING_TITLE_MODEL") or MEETING_TITLE_MODEL


def _safe_profile_summary() -> dict[str, Any]:
    profile = _read_profile()
    key = profile.get("OPENAI_API_KEY") or profile.get("DASHSCOPE_API_KEY") or ""
    base = profile.get("OPENAI_API_BASE", "")
    parsed = urlparse(base) if base else None
    return {
        "profile": "env-or-optional-file",
        "profile_file_exists": bool(PROFILE_PATH and PROFILE_PATH.exists()),
        "base_host": parsed.netloc if parsed else None,
        "base_path": parsed.path if parsed else None,
        "key_present": bool(key),
        "voice_cloning_configured": bool(profile.get("DASHSCOPE_VOICE_API_KEY") or profile.get("DASHSCOPE_API_KEY")),
        "voice_cloning_provider": "dashscope-direct",
        "tts_model": TTS_MODEL,
        "meeting_title_model": _meeting_title_model(),
        "realtime_model": REALTIME_MODEL,
        "asr_channels": ASR_CHANNELS,
        "asr_default_channel": DEFAULT_ASR_CHANNEL,
        "asr_contract": "multi-channel raw_text + corrected_text + public-board event",
        "tts_websocket_url_shape": TOKEN_PLAN_TTS_WS.replace("token-plan.cn-beijing.maas.aliyuncs.com", "[HOST]"),
        "realtime_websocket_url_shape": (TOKEN_PLAN_REALTIME_WS + "?model=" + REALTIME_MODEL).replace(
            "token-plan.cn-beijing.maas.aliyuncs.com", "[HOST]"
        ),
    }


def _fetch_models() -> dict[str, Any]:
    key = _token_plan_key()
    url = _token_plan_base() + "/models"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "User-Agent": "qwen-audio-demo/0.1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    ids = [item.get("id") for item in payload.get("data", []) if isinstance(item, dict)]
    return {"count": len(ids), "model_ids": ids}


def _realtime_model_allowed(model: str) -> bool:
    if not re.fullmatch(r"qwen-audio-[A-Za-z0-9._-]*realtime[A-Za-z0-9._-]*", model):
        return False
    configured = [value.strip() for value in os.getenv("QWEN_REALTIME_MODELS", "").split(",") if value.strip()]
    return not configured or model in configured


def _realtime_model_label(model: str) -> str:
    known = {"qwen-audio-3.0-realtime-plus": "Qwen Audio 3.0 Realtime Plus"}
    return known.get(model, model.replace("qwen-audio-", "Qwen Audio ").replace("-realtime-", " Realtime ").title())


def _available_realtime_models() -> list[dict[str, str]]:
    model_ids = _fetch_models().get("model_ids", [])
    available = [model for model in model_ids if isinstance(model, str) and _realtime_model_allowed(model)]
    if not available:
        available = [REALTIME_MODEL]
    return [{"id": model, "label": _realtime_model_label(model)} for model in dict.fromkeys(available)]


def _tts_blocking(req: TTSRequest) -> dict[str, Any]:
    key = _token_plan_key()
    dashscope.api_key = key
    dashscope.base_websocket_api_url = TOKEN_PLAN_TTS_WS
    audio_format = AudioFormat.MP3_22050HZ_MONO_256KBPS if req.format == "mp3" else AudioFormat.WAV_24000HZ_MONO_16BIT
    started = time.time()
    synthesizer = SpeechSynthesizer(model=TTS_MODEL, voice=req.voice, format=audio_format)
    audio = synthesizer.call(req.text)
    if not audio:
        raise RuntimeError("TTS returned empty audio")
    return {
        "audio": audio,
        "elapsed_ms": round((time.time() - started) * 1000),
        "request_id": getattr(synthesizer, "get_last_request_id", lambda: None)(),
        "first_package_delay_ms": getattr(synthesizer, "get_first_package_delay", lambda: None)(),
        "sha256_12": hashlib.sha256(audio).hexdigest()[:12],
    }


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/assets/transcript-state.js")
def transcript_state_asset() -> FileResponse:
    return FileResponse(STATIC_DIR / "transcript-state.js", media_type="text/javascript")


@app.head("/")
def index_head() -> Response:
    return Response(status_code=200, media_type="text/html")


@app.get("/api/status")
def status() -> JSONResponse:
    result = _safe_profile_summary()
    try:
        result["models"] = _fetch_models()
        result["models_ok"] = True
    except Exception as exc:  # keep status page usable if listing fails
        result["models_ok"] = False
        result["models_error"] = type(exc).__name__ + ": " + str(exc)[:300]
    return JSONResponse(result)


@app.get("/api/realtime/models")
def realtime_models() -> JSONResponse:
    try:
        models = _available_realtime_models()
    except Exception as exc:
        logger.warning("Realtime model discovery failed: %s", type(exc).__name__)
        models = [{"id": REALTIME_MODEL, "label": _realtime_model_label(REALTIME_MODEL)}]
    default_model = REALTIME_MODEL if any(item["id"] == REALTIME_MODEL for item in models) else models[0]["id"]
    return JSONResponse({"default": default_model, "models": models})


def _validated_record_key(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", normalized):
        raise HTTPException(status_code=400, detail=f"invalid {label}")
    return normalized


def _normalized_account(value: str) -> str:
    account = value.strip().casefold()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.+@-]{2,79}", account):
        raise HTTPException(status_code=400, detail="账号需为 3–80 位字母、数字或 @ . _ + -")
    return account


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat()


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)


def provision_managed_account(account: str, password: str, display_name: str | None = None) -> dict[str, str]:
    """Create an invited account from trusted server-side tooling; never exposed as an HTTP route."""
    normalized = _normalized_account(account)
    if not 8 <= len(password) <= 128:
        raise ValueError("password must be 8–128 characters")
    name = (display_name or normalized.split("@", 1)[0]).strip()
    if not 1 <= len(name) <= 40:
        raise ValueError("display name must be 1–40 characters")
    salt = secrets.token_bytes(16)
    user_id = "usr_" + secrets.token_urlsafe(18)
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        try:
            connection.execute(
                "INSERT INTO accounts (id, account, display_name, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, normalized, name, salt, _password_hash(password, salt), _iso_utc()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("account already exists") from exc
        connection.commit()
    return {"id": user_id, "account": normalized, "display_name": name}


def _meeting_db() -> sqlite3.Connection:
    MEETING_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(MEETING_DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            account TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_salt BLOB NOT NULL,
            password_hash BLOB NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            csrf_token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meeting_records (
            owner_id TEXT NOT NULL,
            meeting_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            transcript_json TEXT NOT NULL DEFAULT '[]',
            summary_title TEXT NOT NULL DEFAULT '',
            summary_content TEXT NOT NULL DEFAULT '',
            preview TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (owner_id, meeting_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_records (
            owner_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            title TEXT NOT NULL,
            model TEXT NOT NULL,
            voice TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            messages_json TEXT NOT NULL DEFAULT '[]',
            preview TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (owner_id, conversation_id)
        )
        """
    )
    connection.commit()
    return connection


def _create_auth_session(connection: sqlite3.Connection, user_id: str) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    now = _utc_now()
    connection.execute(
        "INSERT INTO auth_sessions (token_hash, user_id, csrf_token, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
        (hashlib.sha256(token.encode("utf-8")).hexdigest(), user_id, csrf_token, _iso_utc(now), _iso_utc(now + timedelta(days=AUTH_SESSION_DAYS))),
    )
    return token, csrf_token


def _auth_row(request: Request, *, required: bool = True) -> sqlite3.Row | None:
    token = request.cookies.get(AUTH_COOKIE_NAME, "")
    if not token:
        if required:
            raise HTTPException(status_code=401, detail="请先登录")
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        row = connection.execute(
            """
            SELECT s.token_hash, s.user_id, s.csrf_token, s.expires_at, a.account, a.display_name
            FROM auth_sessions AS s JOIN accounts AS a ON a.id = s.user_id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if row and datetime.fromisoformat(row["expires_at"]) <= _utc_now():
            connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
            connection.commit()
            row = None
    if row is None and required:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return row


def _require_csrf(request: Request, auth: sqlite3.Row) -> None:
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not hmac.compare_digest(supplied, auth["csrf_token"]):
        raise HTTPException(status_code=403, detail="无效的请求令牌")


def _auth_payload(row: sqlite3.Row, csrf_token: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "authenticated": True,
        "user": {"id": row["user_id"] if "user_id" in row.keys() else row["id"], "account": row["account"], "display_name": row["display_name"]},
    }
    if csrf_token is not None:
        payload["csrf_token"] = csrf_token
    return payload


def _set_auth_cookie(response: JSONResponse, request: Request, token: str) -> None:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=AUTH_SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=request.url.scheme == "https" or forwarded_proto == "https",
        samesite="lax",
        path="/",
    )


@app.post("/api/auth/register")
def register() -> JSONResponse:
    raise HTTPException(status_code=403, detail="账号仅由管理员创建，暂不开放注册")


@app.post("/api/auth/login")
def login(credentials: AccountCredentials, request: Request) -> JSONResponse:
    account = _normalized_account(credentials.account)
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        row = connection.execute("SELECT * FROM accounts WHERE account = ?", (account,)).fetchone()
        valid = bool(row and hmac.compare_digest(row["password_hash"], _password_hash(credentials.password, row["password_salt"])))
        if not valid:
            raise HTTPException(status_code=401, detail="账号或密码不正确")
        token, csrf_token = _create_auth_session(connection, row["id"])
        connection.commit()
    response = JSONResponse({"authenticated": True, "user": {"id": row["id"], "account": row["account"], "display_name": row["display_name"]}, "csrf_token": csrf_token})
    _set_auth_cookie(response, request, token)
    return response


@app.get("/api/auth/session")
def auth_session(request: Request) -> JSONResponse:
    row = _auth_row(request, required=False)
    return JSONResponse(_auth_payload(row, row["csrf_token"]) if row else {"authenticated": False})


@app.post("/api/auth/logout")
def logout(request: Request) -> JSONResponse:
    row = _auth_row(request)
    _require_csrf(request, row)
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (row["token_hash"],))
        connection.commit()
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response


def _meeting_row_payload(row: sqlite3.Row, include_content: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": row["meeting_id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "duration_seconds": row["duration_seconds"],
        "preview": row["preview"],
    }
    if include_content:
        try:
            payload["transcript_segments"] = json.loads(row["transcript_json"])
        except Exception:
            payload["transcript_segments"] = []
        payload["summary_title"] = row["summary_title"]
        payload["summary_content"] = row["summary_content"]
    return payload


def _conversation_row_payload(row: sqlite3.Row, include_content: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": row["conversation_id"],
        "title": row["title"],
        "model": row["model"],
        "voice": row["voice"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "preview": row["preview"],
    }
    if include_content:
        try:
            payload["messages"] = json.loads(row["messages_json"])
        except Exception:
            payload["messages"] = []
    return payload


@app.get("/api/meetings")
def list_meetings(request: Request) -> JSONResponse:
    owner_id = _auth_row(request)["user_id"]
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        rows = connection.execute(
            "SELECT * FROM meeting_records WHERE owner_id = ? ORDER BY updated_at DESC LIMIT 100",
            (owner_id,),
        ).fetchall()
    return JSONResponse({"meetings": [_meeting_row_payload(row, False) for row in rows]})


@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: str, request: Request) -> JSONResponse:
    owner_id = _auth_row(request)["user_id"]
    record_id = _validated_record_key(meeting_id, "meeting id")
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        row = connection.execute(
            "SELECT * FROM meeting_records WHERE owner_id = ? AND meeting_id = ?",
            (owner_id, record_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return JSONResponse(_meeting_row_payload(row, True))


@app.put("/api/meetings/{meeting_id}")
def upsert_meeting(meeting_id: str, record: MeetingRecordInput, request: Request) -> JSONResponse:
    auth = _auth_row(request)
    _require_csrf(request, auth)
    owner_id = auth["user_id"]
    record_id = _validated_record_key(meeting_id, "meeting id")
    segments = [segment.model_dump() for segment in record.transcript_segments]
    preview = " ".join(segment["text"] for segment in segments)[:120]
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        connection.execute(
            """
            INSERT INTO meeting_records (
                owner_id, meeting_id, title, created_at, updated_at, duration_seconds,
                transcript_json, summary_title, summary_content, preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner_id, meeting_id) DO UPDATE SET
                title = excluded.title,
                updated_at = excluded.updated_at,
                duration_seconds = excluded.duration_seconds,
                transcript_json = excluded.transcript_json,
                summary_title = excluded.summary_title,
                summary_content = excluded.summary_content,
                preview = excluded.preview
            """,
            (
                owner_id,
                record_id,
                record.title.strip() or "新录音",
                record.created_at,
                record.updated_at,
                record.duration_seconds,
                json.dumps(segments, ensure_ascii=False),
                record.summary_title,
                record.summary_content,
                preview,
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM meeting_records WHERE owner_id = ? AND meeting_id = ?",
            (owner_id, record_id),
        ).fetchone()
    return JSONResponse(_meeting_row_payload(row, True))


@app.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: str, request: Request) -> JSONResponse:
    auth = _auth_row(request)
    _require_csrf(request, auth)
    owner_id = auth["user_id"]
    record_id = _validated_record_key(meeting_id, "meeting id")
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        cursor = connection.execute(
            "DELETE FROM meeting_records WHERE owner_id = ? AND meeting_id = ?",
            (owner_id, record_id),
        )
        connection.commit()
    return JSONResponse({"deleted": cursor.rowcount > 0, "id": record_id})


@app.get("/api/conversations")
def list_conversations(request: Request) -> JSONResponse:
    owner_id = _auth_row(request)["user_id"]
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        rows = connection.execute(
            "SELECT * FROM conversation_records WHERE owner_id = ? ORDER BY updated_at DESC LIMIT 100",
            (owner_id,),
        ).fetchall()
    return JSONResponse({"conversations": [_conversation_row_payload(row, False) for row in rows]})


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str, request: Request) -> JSONResponse:
    owner_id = _auth_row(request)["user_id"]
    record_id = _validated_record_key(conversation_id, "conversation id")
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        row = connection.execute(
            "SELECT * FROM conversation_records WHERE owner_id = ? AND conversation_id = ?",
            (owner_id, record_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return JSONResponse(_conversation_row_payload(row, True))


@app.put("/api/conversations/{conversation_id}")
def upsert_conversation(conversation_id: str, record: ConversationRecordInput, request: Request) -> JSONResponse:
    auth = _auth_row(request)
    _require_csrf(request, auth)
    owner_id = auth["user_id"]
    record_id = _validated_record_key(conversation_id, "conversation id")
    messages = [message.model_dump() for message in record.messages]
    preview = next((message["text"] for message in reversed(messages) if message["text"].strip()), "")[:120]
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        connection.execute(
            """
            INSERT INTO conversation_records (
                owner_id, conversation_id, title, model, voice, created_at, updated_at, messages_json, preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner_id, conversation_id) DO UPDATE SET
                title = excluded.title,
                model = excluded.model,
                voice = excluded.voice,
                updated_at = excluded.updated_at,
                messages_json = excluded.messages_json,
                preview = excluded.preview
            """,
            (
                owner_id,
                record_id,
                record.title.strip() or "新对话",
                record.model,
                record.voice,
                record.created_at,
                record.updated_at,
                json.dumps(messages, ensure_ascii=False),
                preview,
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM conversation_records WHERE owner_id = ? AND conversation_id = ?",
            (owner_id, record_id),
        ).fetchone()
    return JSONResponse(_conversation_row_payload(row, True))


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, request: Request) -> JSONResponse:
    auth = _auth_row(request)
    _require_csrf(request, auth)
    owner_id = auth["user_id"]
    record_id = _validated_record_key(conversation_id, "conversation id")
    with _MEETING_DB_LOCK, closing(_meeting_db()) as connection:
        cursor = connection.execute(
            "DELETE FROM conversation_records WHERE owner_id = ? AND conversation_id = ?",
            (owner_id, record_id),
        )
        connection.commit()
    return JSONResponse({"deleted": cursor.rowcount > 0, "id": record_id})


@app.post("/api/tts")
async def tts(req: TTSRequest) -> Response:
    text = " ".join(req.text.split())
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")
    safe_req = TTSRequest(text=text, voice=req.voice, format=req.format)
    try:
        result = await asyncio.to_thread(_tts_blocking, safe_req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error_type": type(exc).__name__, "message": str(exc)[:600]}) from exc
    media_type = "audio/mpeg" if req.format == "mp3" else "audio/wav"
    suffix = "mp3" if req.format == "mp3" else "wav"
    headers = {
        "X-Qwen-Model": TTS_MODEL,
        "X-Qwen-Voice": req.voice,
        "X-Qwen-Request-Id": str(result.get("request_id") or ""),
        "X-Audio-Bytes": str(len(result["audio"])),
        "X-Audio-Sha256-12": str(result.get("sha256_12") or ""),
        "X-Elapsed-Ms": str(result.get("elapsed_ms") or ""),
        "Content-Disposition": f'inline; filename="qwen-token-plan-tts.{suffix}"',
    }
    return Response(content=result["audio"], media_type=media_type, headers=headers)


def _validate_public_audio_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("audio_url must be an http(s) URL accessible by Qwen voice enrollment")
    return url


def _create_voice_blocking(req: VoiceCloneRequest) -> dict[str, Any]:
    key = _voice_cloning_key()
    _validate_public_audio_url(req.audio_url)
    dashscope.api_key = key
    dashscope.base_http_api_url = DASHSCOPE_HTTP_API_BASE
    from dashscope.audio.tts_v2 import VoiceEnrollmentService

    service = VoiceEnrollmentService(api_key=key)
    voice_id = service.create_voice(
        target_model=req.target_model,
        prefix=req.prefix,
        url=req.audio_url,
        language_hints=req.language_hints or None,
        max_prompt_audio_length=req.max_prompt_audio_length,
    )
    return {"voice_id": voice_id, "target_model": req.target_model, "request_id": service.get_last_request_id()}


@app.post("/api/voice-cloning/create")
async def voice_cloning_create(req: VoiceCloneRequest) -> JSONResponse:
    try:
        result = await asyncio.to_thread(_create_voice_blocking, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error_type": type(exc).__name__, "message": str(exc)[:700]}) from exc
    return JSONResponse(result)


@app.get("/api/voice-cloning/list")
def voice_cloning_list(prefix: str | None = None) -> JSONResponse:
    try:
        key = _voice_cloning_key()
        dashscope.base_http_api_url = DASHSCOPE_HTTP_API_BASE
        from dashscope.audio.tts_v2 import VoiceEnrollmentService

        service = VoiceEnrollmentService(api_key=key)
        voices = service.list_voices(prefix=prefix)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error_type": type(exc).__name__, "message": str(exc)[:700]}) from exc
    return JSONResponse({"voices": voices})


def _meeting_notes_blocking(req: MeetingNotesRequest) -> dict[str, Any]:
    key = _token_plan_key()
    model = _meeting_notes_model(req.model)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是会议纪要实时整理助手，只输出中文结构化结果。"},
            {"role": "user", "content": req.instruction + "\n\n转写文本：\n" + req.transcript},
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        _token_plan_base() + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "qwen-audio-demo-meeting-notes/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=80) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = ""
    try:
        content = body["choices"][0]["message"]["content"]
    except Exception:
        content = json.dumps(body, ensure_ascii=False)[:4000]
    return {"model": model, "content": content, "raw_usage": body.get("usage")}


@app.post("/api/meeting-notes/polish")
async def meeting_notes_polish(req: MeetingNotesRequest) -> JSONResponse:
    try:
        result = await asyncio.to_thread(_meeting_notes_blocking, req)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:700]
        raise HTTPException(status_code=502, detail={"error_type": "HTTPError", "status": exc.code, "message": detail}) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error_type": type(exc).__name__, "message": str(exc)[:700]}) from exc
    return JSONResponse(result)


def _normalize_meeting_title(value: str) -> str:
    title = str(value or "").strip().splitlines()[0].strip()
    title = re.sub(r"^(?:会议)?标题\s*[:：]\s*", "", title)
    title = title.strip(" `#*\"'《》【】[]（）()")
    title = re.sub(r"[。！？!?；;，,：:]+$", "", title).strip()
    title = title.strip(" `#*\"'《》【】[]（）()")
    title = re.sub(r"\s+", " ", title)
    return title[:28] or "新录音"


def _meeting_title_blocking(req: MeetingTitleRequest) -> dict[str, Any]:
    key = _token_plan_key()
    model = _meeting_title_model(req.model)
    transcript = " ".join(req.transcript.split())[:2400]
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是会议标题编辑。根据转写生成一个具体、自然的中文标题。硬性限制为8到18个汉字，超过18个即不合格；只保留核心主题和动作，例如‘实时转写与标题生成优化’。不要书名号、引号、句号、解释或‘会议标题’前缀，只输出标题。",
            },
            {"role": "user", "content": transcript},
        ],
        "temperature": 0.1,
        "max_tokens": 64,
        "enable_thinking": False,
    }
    request = urllib.request.Request(
        _token_plan_base() + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "qwen-audio-demo-meeting-title/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    try:
        content = body["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError("meeting title model returned an invalid response") from exc
    return {"model": model, "title": _normalize_meeting_title(content), "raw_usage": body.get("usage")}


@app.post("/api/meeting-title")
async def meeting_title(req: MeetingTitleRequest) -> JSONResponse:
    transcript = " ".join(req.transcript.split())
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript is empty")
    safe_req = MeetingTitleRequest(transcript=transcript, model=req.model)
    try:
        result = await asyncio.to_thread(_meeting_title_blocking, safe_req)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:700]
        raise HTTPException(status_code=502, detail={"error_type": "HTTPError", "status": exc.code, "message": detail}) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error_type": type(exc).__name__, "message": str(exc)[:700]}) from exc
    return JSONResponse(result)


def _collapse_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _simple_chinese_correction(raw_text: str) -> str:
    """Tiny local post-process so raw/corrected UI works before LLM correction is wired."""
    text = _collapse_text(raw_text)
    for filler in ("呃", "嗯", "啊", "额"):
        text = text.replace(filler, "")
    text = text.replace(" ,", "，").replace(" .", "。")
    if text and text[-1] not in "。！？.!?":
        text += "。"
    return text or raw_text


def normalize_asr_result(channel: str, raw_text: str, corrected_text: str | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = _collapse_text(raw_text)
    corrected = _collapse_text(corrected_text or "") or _simple_chinese_correction(raw)
    return {
        "channel": channel,
        "raw_text": raw,
        "corrected_text": corrected,
        "meta": meta or {},
        "board_event": {
            "demo_event": "transcript.delta",
            "role": "user",
            "phase": "final",
            "text": corrected,
            "raw_text": raw,
            "source_type": f"asr.{channel}",
        },
    }


def _write_upload_to_temp(audio_bytes: bytes, filename: str) -> Path:
    suffix = Path(filename or "audio.wav").suffix or ".wav"
    temp_dir = PROJECT_ROOT / "playground" / "asr-temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="qwen-demo-asr-", suffix=suffix, dir=str(temp_dir))
    path = Path(name)
    with os.fdopen(fd, "wb") as fh:
        fh.write(audio_bytes)
    return path


def _cleanup_asr_temp_file(path: Path | None) -> None:
    if path is None:
        return
    try:
        resolved = path.resolve()
        temp_root = (PROJECT_ROOT / "playground" / "asr-temp").resolve()
        if temp_root in resolved.parents or resolved == temp_root:
            resolved.unlink(missing_ok=True)
    except Exception:
        pass


def _convert_to_wav_if_needed(path: Path) -> Path:
    if path.suffix.lower() == ".wav":
        return path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return path
    out = path.with_suffix(".wav")
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000", str(out)],
        check=True,
        timeout=45,
    )
    return out


def _stub_asr(audio_bytes: bytes, filename: str) -> dict[str, Any]:
    seconds: float | None = None
    if filename.lower().endswith(".wav"):
        temp_path: Path | None = None
        try:
            temp_path = _write_upload_to_temp(audio_bytes, filename)
            with wave.open(str(temp_path), "rb") as wf:
                seconds = round(wf.getnframes() / float(wf.getframerate()), 3)
        except Exception:
            seconds = None
        finally:
            _cleanup_asr_temp_file(temp_path)
    text = "这是本地合同通道：音频已上传，ASR 多渠道页面和公屏链路已打通。"
    return normalize_asr_result("stub-local", text, text, {"engine": "stub", "audio_bytes": len(audio_bytes), "seconds": seconds})


def _strip_sensevoice_tags(text: str) -> str:
    """Remove SenseVoice control tags like <|zh|><|NEUTRAL|><|Speech|><|withitn|>."""
    return _collapse_text(re.sub(r"<\|[^|>]+\|>", "", text or ""))


def _extract_funasr_text(result: Any) -> str:
    if isinstance(result, str):
        return _strip_sensevoice_tags(result)
    if isinstance(result, dict):
        for key in ("text", "raw_text"):
            value = result.get(key)
            if isinstance(value, str) and value:
                return _strip_sensevoice_tags(value)
        sentence_info = result.get("sentence_info")
        if isinstance(sentence_info, list):
            parts = [str(x.get("text", "")) for x in sentence_info if isinstance(x, dict)]
            return _strip_sensevoice_tags("".join(parts))
    if isinstance(result, list):
        return _strip_sensevoice_tags("".join(_extract_funasr_text(item) for item in result))
    return ""


def _funasr_worker_python(device: str) -> Path | None:
    candidates: list[Path] = []
    env_venv = os.getenv("ASR_GPU_VENV", "").strip()
    if str(device).startswith("cuda"):
        if env_venv:
            candidates.append(Path(env_venv).expanduser() / "bin" / "python")
        candidates.append(PROJECT_ROOT / ".venv-asr-gpu-cu121" / "bin" / "python")
        candidates.append(PROJECT_ROOT / ".venv-asr-gpu" / "bin" / "python")
    candidates.append(PROJECT_ROOT / ".venv-asr" / "bin" / "python")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _get_cached_funasr_model(model_name: str, device: str) -> tuple[Any, threading.Lock]:
    """Load one in-process model per device and serialize inference on it."""
    key = (model_name, device)
    with _FUNASR_CACHE_LOCK:
        model = _FUNASR_MODELS.get(key)
        model_lock = _FUNASR_MODEL_LOCKS.setdefault(key, threading.Lock())
        if model is None:
            from funasr import AutoModel  # type: ignore

            started = time.monotonic()
            logger.info("FunASR model loading model=%s device=%s", model_name, device)
            model = AutoModel(model=model_name, device=device, disable_update=True)
            _FUNASR_MODELS[key] = model
            logger.info(
                "FunASR model ready model=%s device=%s elapsed_ms=%d",
                model_name,
                device,
                round((time.monotonic() - started) * 1000),
            )
    return model, model_lock


def _funasr_asr(audio_bytes: bytes, filename: str, channel: str, device: str) -> dict[str, Any]:
    source_path = _write_upload_to_temp(audio_bytes, filename)
    try:
        wav_path = _convert_to_wav_if_needed(source_path)
        model_name = FUNASR_MODEL
        started = time.time()
        cache_root = PROJECT_ROOT / "playground" / "model-cache"
        os.environ.setdefault("MODELSCOPE_CACHE", str(cache_root / "modelscope"))
        os.environ.setdefault("HF_HOME", str(cache_root / "huggingface"))
        os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_root / "transformers"))
        try:
            model, model_lock = _get_cached_funasr_model(model_name, device)
            with model_lock:
                result = model.generate(input=str(wav_path), language="zh", use_itn=True)
            raw_text = _extract_funasr_text(result)
            meta = {
                "engine": "funasr",
                "model": model_name,
                "device": device,
                "channel": channel,
                "elapsed_ms": round((time.time() - started) * 1000),
            }
        except Exception as inproc_exc:
            worker_python = _funasr_worker_python(device)
            worker = PROJECT_ROOT / "scripts" / "funasr_worker.py"
            if worker_python is None:
                raise RuntimeError(
                    f"FunASR {channel} worker is not ready. Create .venv-asr-gpu with CUDA PyTorch/FunASR "
                    f"for funasr-gpu, or choose stub-local for contract smoke. In-process error: {type(inproc_exc).__name__}: {str(inproc_exc)[:200]}"
                ) from inproc_exc
            proc = subprocess.run(
                [str(worker_python), str(worker), str(wav_path), "--model", model_name, "--device", device],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=240,
            )
            json_lines = [line for line in proc.stdout.splitlines() if line.strip().startswith("{")]
            try:
                payload = json.loads(json_lines[-1] if json_lines else "{}")
            except Exception as exc:
                raise RuntimeError(f"FunASR worker returned non-JSON output: {proc.stdout[:300]} {proc.stderr[:300]}") from exc
            if proc.returncode != 0 or not payload.get("ok"):
                raise RuntimeError(f"FunASR worker failed: {payload.get('error_type')}: {payload.get('message')}") from inproc_exc
            raw_text = str(payload.get("text") or "")
            meta = dict(payload.get("meta") or {})
            meta.update({"channel": channel, "device": meta.get("device") or device, "elapsed_ms": meta.get("elapsed_ms") or round((time.time() - started) * 1000)})
        if not any(char.isalnum() for char in raw_text):
            raw_text = ""
        meta["speech_detected"] = bool(raw_text)
        return normalize_asr_result(channel, raw_text, _simple_chinese_correction(raw_text), meta)
    finally:
        try:
            if 'wav_path' in locals() and wav_path != source_path:
                _cleanup_asr_temp_file(wav_path)
        finally:
            _cleanup_asr_temp_file(source_path)


def _funasr_cpu_asr(audio_bytes: bytes, filename: str) -> dict[str, Any]:
    return _funasr_asr(audio_bytes, filename, "funasr-cpu", "cpu")


def _funasr_gpu_asr(audio_bytes: bytes, filename: str) -> dict[str, Any]:
    return _funasr_asr(audio_bytes, filename, "funasr-gpu", FUNASR_GPU_DEVICE)


def transcribe_audio_bytes(channel: str, audio_bytes: bytes, filename: str, correct: bool = True) -> dict[str, Any]:
    if not audio_bytes:
        raise ValueError("empty audio upload")
    if len(audio_bytes) > 12 * 1024 * 1024:
        raise ValueError("audio upload too large for demo; keep it under 12MB")
    if channel == "stub-local":
        return _stub_asr(audio_bytes, filename)
    if channel == "funasr-gpu":
        result = _funasr_gpu_asr(audio_bytes, filename)
    elif channel == "funasr-cpu":
        result = _funasr_cpu_asr(audio_bytes, filename)
    else:
        raise ValueError(f"unknown ASR channel: {channel}")
    if not correct:
        result["corrected_text"] = result["raw_text"]
        result["board_event"]["text"] = result["raw_text"]
    return result


def pcm16_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


class AsrStreamSession:
    def __init__(
        self,
        channel: str = DEFAULT_ASR_CHANNEL,
        sample_rate: int = 16000,
        chunk_seconds: float = 4.0,
        max_connection_seconds: int = GUEST_ASR_STREAM_SECONDS,
    ) -> None:
        self.channel = self._validate_channel(channel or DEFAULT_ASR_CHANNEL)
        self.sample_rate = self._validate_sample_rate(16000 if sample_rate is None else sample_rate)
        self.chunk_seconds = self._validate_chunk_seconds(chunk_seconds)
        self.max_connection_seconds = max(GUEST_ASR_STREAM_SECONDS, int(max_connection_seconds))
        self.buffer = bytearray()
        self.history = bytearray()
        self.chunk_index = 0
        self.window_index = 1
        self.total_pcm_bytes = 0
        self.last_revision_total_bytes = 0

    @staticmethod
    def _validate_channel(channel: str) -> str:
        if channel not in ASR_CHANNELS:
            raise ValueError("unknown ASR channel; choose funasr-gpu, funasr-cpu, or stub-local")
        return channel

    @staticmethod
    def _validate_sample_rate(sample_rate: int) -> int:
        try:
            value = int(sample_rate)
        except Exception as exc:
            raise ValueError("sample_rate must be one of 8000, 16000, 24000, 48000") from exc
        if value not in ALLOWED_ASR_STREAM_SAMPLE_RATES:
            raise ValueError("sample_rate must be one of 8000, 16000, 24000, 48000")
        return value

    @staticmethod
    def _validate_chunk_seconds(chunk_seconds: float | int | str | None) -> float:
        try:
            value = float(4.0 if chunk_seconds is None else chunk_seconds)
        except Exception as exc:
            raise ValueError("chunk_seconds must be a number") from exc
        if not math.isfinite(value):
            raise ValueError("chunk_seconds must be finite")
        return max(MIN_ASR_STREAM_CHUNK_SECONDS, min(value, MAX_ASR_STREAM_CHUNK_SECONDS))

    @property
    def chunk_bytes(self) -> int:
        return int(self.sample_rate * self.chunk_seconds * 2)

    @property
    def max_buffer_bytes(self) -> int:
        return int(self.sample_rate * MAX_ASR_STREAM_BUFFER_SECONDS * 2)

    @property
    def max_total_bytes(self) -> int:
        return int(self.sample_rate * self.max_connection_seconds * 2)

    @property
    def context_bytes(self) -> int:
        return int(self.sample_rate * ASR_STREAM_CONTEXT_SECONDS * 2)

    @property
    def should_rotate_window(self) -> bool:
        return len(self.history) >= self.context_bytes

    def append_pcm16(self, chunk: bytes) -> None:
        if not isinstance(chunk, (bytes, bytearray)):
            raise ValueError("audio chunk must be PCM16 bytes")
        if not chunk:
            return
        if len(chunk) > MAX_ASR_STREAM_FRAME_BYTES:
            raise ValueError(f"audio frame too large for demo; max {MAX_ASR_STREAM_FRAME_BYTES} bytes")
        if len(chunk) % 2:
            raise ValueError("audio chunk must contain whole PCM16 samples")
        if self.total_pcm_bytes + len(chunk) > self.max_total_bytes:
            raise ValueError(f"recording segment reached its {self.max_connection_seconds // 60}-minute limit")
        if len(self.buffer) + len(chunk) > self.max_buffer_bytes:
            raise ValueError(f"stream buffer too large for demo; max {MAX_ASR_STREAM_BUFFER_SECONDS:g}s buffered")
        self.buffer.extend(chunk)
        self.history.extend(chunk)
        self.total_pcm_bytes += len(chunk)

    def append_base64_pcm16(self, audio_b64: str) -> None:
        if len(audio_b64 or "") > MAX_ASR_STREAM_JSON_FRAME_BYTES:
            raise ValueError(f"base64 audio frame too large for demo; max {MAX_ASR_STREAM_JSON_FRAME_BYTES} chars")
        try:
            decoded = base64.b64decode(audio_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("audio must be strict base64-encoded PCM16") from exc
        self.append_pcm16(decoded)

    def _next_chunk_index(self) -> int:
        if self.chunk_index >= MAX_ASR_STREAM_CHUNKS_PER_CONNECTION:
            raise ValueError(f"too many ASR chunks for demo; max {MAX_ASR_STREAM_CHUNKS_PER_CONNECTION}")
        self.chunk_index += 1
        return self.chunk_index

    def pop_ready_wavs(self, max_chunks: int = MAX_ASR_STREAM_CHUNKS_PER_RECEIVE) -> list[tuple[int, bytes]]:
        out: list[tuple[int, bytes]] = []
        while len(self.buffer) >= self.chunk_bytes and len(out) < max(0, int(max_chunks)):
            pcm = bytes(self.buffer[: self.chunk_bytes])
            del self.buffer[: self.chunk_bytes]
            out.append((self._next_chunk_index(), pcm16_to_wav_bytes(pcm, self.sample_rate)))
        return out

    def commit_wav(self) -> tuple[int, bytes] | None:
        if not self.buffer:
            return None
        pcm = bytes(self.buffer)
        self.buffer.clear()
        return self._next_chunk_index(), pcm16_to_wav_bytes(pcm, self.sample_rate)

    def pop_ready_revision_wav(self) -> tuple[int, bytes] | None:
        """Re-decode the full session when another interval becomes available."""
        if len(self.history) - self.last_revision_total_bytes < self.chunk_bytes:
            return None
        self.last_revision_total_bytes = len(self.history)
        self.buffer.clear()
        return self._next_chunk_index(), pcm16_to_wav_bytes(bytes(self.history), self.sample_rate)

    def commit_revision_wav(self) -> tuple[int, bytes] | None:
        if not self.history:
            return None
        self.last_revision_total_bytes = len(self.history)
        self.buffer.clear()
        return self._next_chunk_index(), pcm16_to_wav_bytes(bytes(self.history), self.sample_rate)

    def rotate_window(self) -> None:
        self.buffer.clear()
        self.history.clear()
        self.last_revision_total_bytes = 0
        self.window_index += 1


async def _send_asr_stream_result(client: WebSocket, session: AsrStreamSession, index: int, wav_bytes: bytes, final: bool = False) -> None:
    started = time.monotonic()
    logger.info(
        "ASR stream chunk started channel=%s index=%d audio_bytes=%d final=%s",
        session.channel,
        index,
        len(wav_bytes),
        final,
    )
    result = await asyncio.to_thread(transcribe_audio_bytes, session.channel, wav_bytes, f"stream-chunk-{index}.wav", True)
    result["stream"] = {
        "chunk_index": index,
        "revision": index,
        "revision_scope": "window",
        "replace": True,
        "final": final,
        "sample_rate": session.sample_rate,
        "window_index": session.window_index,
    }
    result["board_event"]["phase"] = "final" if final else "partial"
    result["board_event"]["source_type"] = f"asr.stream.{session.channel}"
    result["board_event"]["item_id"] = f"asr-stream-{index}"
    await client.send_json({"demo_event": "asr.stream.result", "result": result, "board_event": result["board_event"]})
    logger.info(
        "ASR stream chunk completed channel=%s index=%d text_chars=%d elapsed_ms=%d final=%s",
        session.channel,
        index,
        len(str(result.get("corrected_text") or "")),
        round((time.monotonic() - started) * 1000),
        final,
    )


async def _close_asr_stream_policy(client: WebSocket, message: str, code: int = 1008) -> None:
    await client.send_json({"demo_event": "asr.stream.error", "message": message})
    await client.close(code=code, reason=message[:120])


async def _finish_asr_stream_at_limit(client: WebSocket, session: AsrStreamSession) -> None:
    committed = session.commit_revision_wav()
    if committed is not None:
        await _send_asr_stream_result(client, session, committed[0], committed[1], final=True)
    await client.send_json({
        "demo_event": "asr.stream.done",
        "final": True,
        "limit_reached": True,
        "max_connection_seconds": session.max_connection_seconds,
    })


@app.websocket("/ws/asr/stream")
async def asr_stream(client: WebSocket) -> None:
    await client.accept()
    authenticated = _auth_row(client, required=False) is not None
    stream_mode = "account" if authenticated else "guest"
    max_connection_seconds = ACCOUNT_ASR_STREAM_SECONDS if authenticated else GUEST_ASR_STREAM_SECONDS
    session = AsrStreamSession(max_connection_seconds=max_connection_seconds)
    await client.send_json({
        "demo_event": "asr.stream.ready",
        "channel": session.channel,
        "sample_rate": session.sample_rate,
        "chunk_seconds": session.chunk_seconds,
        "stream_mode": stream_mode,
        "max_connection_seconds": max_connection_seconds,
        "context_seconds": ASR_STREAM_CONTEXT_SECONDS,
    })
    try:
        while True:
            message = await client.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                try:
                    session.append_pcm16(message["bytes"])
                except ValueError as exc:
                    if str(exc).startswith("recording segment reached"):
                        await _finish_asr_stream_at_limit(client, session)
                    else:
                        await _close_asr_stream_policy(client, str(exc), 1009)
                    break
            elif message.get("text") is not None:
                if len(message["text"]) > MAX_ASR_STREAM_JSON_FRAME_BYTES:
                    await _close_asr_stream_policy(client, f"JSON frame too large for demo; max {MAX_ASR_STREAM_JSON_FRAME_BYTES} chars", 1009)
                    break
                try:
                    payload = json.loads(message["text"])
                except Exception:
                    await client.send_json({"demo_event": "asr.stream.error", "message": "expected JSON text or PCM16 bytes"})
                    continue
                msg_type = payload.get("type")
                if msg_type == "asr.stream.start":
                    try:
                        session = AsrStreamSession(
                            channel=str(payload.get("channel") or DEFAULT_ASR_CHANNEL),
                            sample_rate=payload.get("sample_rate", 16000),
                            chunk_seconds=payload.get("chunk_seconds", 4.0),
                            max_connection_seconds=max_connection_seconds,
                        )
                    except (TypeError, ValueError) as exc:
                        await _close_asr_stream_policy(client, str(exc), 1008)
                        break
                    logger.info(
                        "ASR stream session started channel=%s sample_rate=%d chunk_seconds=%.2f",
                        session.channel,
                        session.sample_rate,
                        session.chunk_seconds,
                    )
                    await client.send_json({
                        "demo_event": "asr.stream.started",
                        "channel": session.channel,
                        "sample_rate": session.sample_rate,
                        "chunk_seconds": session.chunk_seconds,
                        "stream_mode": stream_mode,
                        "max_connection_seconds": max_connection_seconds,
                        "context_seconds": ASR_STREAM_CONTEXT_SECONDS,
                    })
                    continue
                if msg_type == "asr.stream.append":
                    try:
                        session.append_base64_pcm16(str(payload.get("audio") or ""))
                    except ValueError as exc:
                        if str(exc).startswith("recording segment reached"):
                            await _finish_asr_stream_at_limit(client, session)
                        else:
                            await _close_asr_stream_policy(client, str(exc), 1009)
                        break
                elif msg_type in {"asr.stream.commit", "asr.stream.finish"}:
                    try:
                        committed = session.commit_revision_wav()
                        if committed is not None:
                            await _send_asr_stream_result(client, session, committed[0], committed[1], final=True)
                        if msg_type == "asr.stream.commit":
                            session.rotate_window()
                    except ValueError as exc:
                        await _close_asr_stream_policy(client, str(exc), 1009)
                        break
                    await client.send_json({
                        "demo_event": "asr.stream.done",
                        "final": msg_type == "asr.stream.finish",
                        "rollover": msg_type == "asr.stream.commit",
                        "window_index": session.window_index,
                    })
                    if msg_type == "asr.stream.finish":
                        break
                    continue
                else:
                    await client.send_json({"demo_event": "asr.stream.error", "message": "unknown ASR stream message type"})
                    continue
            try:
                revision_wav = session.pop_ready_revision_wav()
                if revision_wav is not None:
                    rollover = session.should_rotate_window
                    await _send_asr_stream_result(client, session, revision_wav[0], revision_wav[1], final=rollover)
                    if rollover:
                        session.rotate_window()
                        await client.send_json({
                            "demo_event": "asr.stream.done",
                            "final": False,
                            "rollover": True,
                            "window_index": session.window_index,
                        })
            except ValueError as exc:
                await _close_asr_stream_policy(client, str(exc), 1009)
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ASR stream failed: %s", type(exc).__name__)
        try:
            await client.send_json({"demo_event": "asr.stream.error", "error_type": type(exc).__name__, "message": "stream ASR failed; retry with a smaller chunk or stub-local"})
        except Exception:
            pass
    finally:
        try:
            await client.close()
        except Exception:
            pass


@app.get("/api/asr/channels")
def asr_channels(request: Request) -> JSONResponse:
    authenticated = _auth_row(request, required=False) is not None
    return JSONResponse({
        "default": DEFAULT_ASR_CHANNEL,
        "channels": ASR_CHANNELS,
        "stream_policy": {
            "mode": "account" if authenticated else "guest",
            "max_connection_seconds": ACCOUNT_ASR_STREAM_SECONDS if authenticated else GUEST_ASR_STREAM_SECONDS,
            "context_seconds": ASR_STREAM_CONTEXT_SECONDS,
            "pause_counts_toward_limit": False,
            "can_continue_existing_meeting": True,
        },
    })


@app.post("/api/asr")
async def asr_upload(
    file: UploadFile = File(...),
    channel: str = Form(DEFAULT_ASR_CHANNEL),
    correct: bool = Form(True),
) -> JSONResponse:
    try:
        audio_bytes = await file.read()
        result = await asyncio.to_thread(transcribe_audio_bytes, channel, audio_bytes, file.filename or "audio.wav", correct)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error_type": type(exc).__name__, "message": str(exc)[:700]}) from exc
    return JSONResponse(result)


async def _connect_upstream(url: str, key: str):
    if websockets is None:
        raise RuntimeError("websockets package is not installed")
    headers = {"Authorization": f"Bearer {key}", "User-Agent": "qwen-audio-demo-realtime-proxy/0.1"}
    try:
        return await websockets.connect(url, additional_headers=headers, ping_interval=20, ping_timeout=20, max_size=8_000_000)
    except TypeError:
        return await websockets.connect(url, extra_headers=headers, ping_interval=20, ping_timeout=20, max_size=8_000_000)


def _event_text(event: dict[str, Any], field_order: tuple[str, ...] = ("delta", "transcript", "text")) -> tuple[str, str | None]:
    """Return text-like content from a Qwen Realtime event without exposing binary/audio payloads."""
    for field in field_order:
        value = event.get(field)
        if isinstance(value, str) and value:
            return value, field
    for container_key in ("part", "content", "item", "response"):
        container = event.get(container_key)
        if isinstance(container, dict):
            for field in field_order:
                value = container.get(field)
                if isinstance(value, str) and value:
                    return value, f"{container_key}.{field}"
    return "", None


def extract_realtime_transcript_events(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Qwen Realtime transcript/text events for the browser public board.

    The raw Realtime stream remains available in the debug event log, but the UI
    should not force users to read JSON. This function extracts the events called
    out in the official docs, including:
    - conversation.item.input_audio_transcription.completed -> user transcript
    - response.audio_transcript.delta/done -> assistant transcript
    - response.text.delta / response.output_text.delta -> assistant text
    - conversation.item.ambient_audio_transcription.delta/completed -> ambient text
    """
    event_type = event.get("type")
    if not isinstance(event_type, str):
        return []

    mapping: dict[str, tuple[str, str, tuple[str, ...]]] = {
        "conversation.item.input_audio_transcription.delta": ("user", "delta", ("delta", "transcript", "text")),
        "conversation.item.input_audio_transcription.completed": ("user", "final", ("transcript", "text", "delta")),
        "conversation.item.ambient_audio_transcription.delta": ("ambient", "delta", ("text", "delta", "transcript")),
        "conversation.item.ambient_audio_transcription.completed": ("ambient", "final", ("text", "transcript", "delta")),
        "response.audio_transcript.delta": ("assistant", "delta", ("delta", "transcript", "text")),
        "response.audio_transcript.done": ("assistant", "final", ("transcript", "text", "delta")),
        "response.text.delta": ("assistant", "delta", ("delta", "text", "transcript")),
        "response.text.done": ("assistant", "final", ("text", "transcript", "delta")),
        "response.output_text.delta": ("assistant", "delta", ("delta", "text", "transcript")),
        "response.output_text.done": ("assistant", "final", ("text", "transcript", "delta")),
    }
    if event_type in mapping:
        role, phase, fields = mapping[event_type]
        text, source_field = _event_text(event, fields)
        if text:
            return [
                {
                    "demo_event": "transcript.delta",
                    "role": role,
                    "phase": phase,
                    "text": text,
                    "source_type": event_type,
                    "source_field": source_field,
                    "item_id": event.get("item_id") or event.get("item", {}).get("id") if isinstance(event.get("item"), dict) else event.get("item_id"),
                    "response_id": event.get("response_id") or event.get("response", {}).get("id") if isinstance(event.get("response"), dict) else event.get("response_id"),
                }
            ]
        return []

    if event_type in {"conversation.item.created", "response.output_item.done"}:
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        role = item.get("role") or event.get("role") or "unknown"
        normalized_role = "assistant" if role in {"assistant", "ai"} else "user" if role == "user" else "unknown"
        out: list[dict[str, Any]] = []
        content = item.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("transcript") or part.get("text")
                if isinstance(text, str) and text:
                    out.append(
                        {
                            "demo_event": "transcript.delta",
                            "role": normalized_role,
                            "phase": "final",
                            "text": text,
                            "source_type": event_type,
                            "source_field": "item.content.transcript/text",
                            "item_id": item.get("id") or event.get("item_id"),
                            "response_id": event.get("response_id"),
                        }
                    )
        return out

    return []


def _redact_event_for_browser_log(event: dict[str, Any]) -> dict[str, Any]:
    """Keep debug logs readable by omitting huge base64 audio deltas."""
    if event.get("type") == "response.audio.delta" and isinstance(event.get("delta"), str):
        safe = dict(event)
        safe["delta"] = f"<audio b64 omitted, length={len(event['delta'])}>"
        return safe
    return event


@app.websocket("/ws/realtime")
async def realtime_proxy(client: WebSocket) -> None:
    await client.accept()
    requested_model = client.query_params.get("model", REALTIME_MODEL).strip()
    if not _realtime_model_allowed(requested_model):
        await client.send_json({"demo_event": "proxy.error", "message": "不支持的实时模型"})
        await client.close(code=1008)
        return
    key = _token_plan_key()
    upstream_url = f"{TOKEN_PLAN_REALTIME_WS}?model={requested_model}"
    upstream = None
    try:
        upstream = await _connect_upstream(upstream_url, key)
        await client.send_json({"demo_event": "proxy.connected", "upstream": "token-plan-api-ws-v1-realtime", "model": requested_model})

        async def upstream_to_client() -> None:
            async for message in upstream:
                if isinstance(message, bytes):
                    await client.send_json({"demo_event": "upstream.binary", "bytes": len(message)})
                    continue
                try:
                    event = json.loads(message)
                except Exception:
                    await client.send_text(message)
                    continue
                for transcript_event in extract_realtime_transcript_events(event):
                    await client.send_json(transcript_event)
                if event.get("type") == "response.audio.delta" and isinstance(event.get("delta"), str):
                    await client.send_json(
                        {
                            "demo_event": "audio.delta",
                            "audio": event["delta"],
                            "response_id": event.get("response_id"),
                            "item_id": event.get("item_id"),
                            "sample_rate": 24000,
                        }
                    )
                await client.send_json({"demo_event": "upstream.event", "event": _redact_event_for_browser_log(event)})

        async def client_to_upstream() -> None:
            while True:
                message = await client.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("text") is not None:
                    if len(message["text"]) > MAX_ASR_STREAM_JSON_FRAME_BYTES:
                        await client.send_json({"demo_event": "proxy.error", "message": "realtime message is too large"})
                        continue
                    await upstream.send(message["text"])
                elif message.get("bytes") is not None:
                    if len(message["bytes"]) > MAX_ASR_STREAM_FRAME_BYTES:
                        await client.send_json({"demo_event": "proxy.error", "message": "realtime binary frame is too large"})
                        continue
                    await upstream.send(message["bytes"])

        done, pending = await asyncio.wait(
            {asyncio.create_task(upstream_to_client()), asyncio.create_task(client_to_upstream())},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                raise exc
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await client.send_json({"demo_event": "proxy.error", "error_type": type(exc).__name__, "message": str(exc)[:500]})
        except Exception:
            pass
    finally:
        if upstream is not None:
            await upstream.close()
        try:
            await client.close()
        except Exception:
            pass
