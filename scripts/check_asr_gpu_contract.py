#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import math
import os
import struct
import tempfile
import wave
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from chatvoice.web import legacy_app as main  # noqa: E402


def make_test_wav(duration_seconds: float = 0.1, sample_rate: int = 16000) -> bytes:
    path = PROJECT_ROOT / "playground" / "asr-gpu-contract-tone.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(int(duration_seconds * sample_rate)):
        value = int(160 * math.sin(2 * math.pi * 440 * (i / sample_rate)))
        frames.append(struct.pack("<h", value))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))
    return path.read_bytes()

checks: dict[str, object] = {}
checks["default_is_funasr_gpu"] = main.DEFAULT_ASR_CHANNEL == "funasr-gpu"
checks["channel_funasr_gpu_exists"] = "funasr-gpu" in main.ASR_CHANNELS
checks["channel_funasr_gpu_cuda"] = main.ASR_CHANNELS.get("funasr-gpu", {}).get("device") in {"cuda", "cuda:0"}
checks["channel_funasr_cpu_not_default"] = "funasr-cpu" in main.ASR_CHANNELS and main.DEFAULT_ASR_CHANNEL != "funasr-cpu"
checks["stream_route_exists"] = any(getattr(route, "path", None) == "/ws/asr/stream" for route in main.app.routes)
checks["pcm16_wav_helper_exists"] = callable(getattr(main, "pcm16_to_wav_bytes", None))
checks["chunk_session_class_exists"] = hasattr(main, "AsrStreamSession")
checks["normalizer_source_type_gpu"] = main.normalize_asr_result("funasr-gpu", "我想嗯测试", "我想测试。", {"engine": "contract"})["board_event"]["source_type"] == "asr.funasr-gpu"
checks["stream_sample_rate_allowlist"] = hasattr(main, "ALLOWED_ASR_STREAM_SAMPLE_RATES") and {8000, 16000, 24000, 48000}.issubset(main.ALLOWED_ASR_STREAM_SAMPLE_RATES)
checks["stream_rejects_invalid_sample_rate"] = False
try:
    main.AsrStreamSession(sample_rate=0)
except ValueError:
    checks["stream_rejects_invalid_sample_rate"] = True
checks["stream_rejects_unknown_channel"] = False
try:
    main.AsrStreamSession(channel="not-a-channel")
except ValueError:
    checks["stream_rejects_unknown_channel"] = True
checks["stream_rejects_nonfinite_chunk_seconds"] = False
try:
    main.AsrStreamSession(channel="stub-local", chunk_seconds="nan")
except ValueError:
    checks["stream_rejects_nonfinite_chunk_seconds"] = True
session = main.AsrStreamSession(channel="stub-local", sample_rate=16000, chunk_seconds=1)
checks["stream_strict_base64"] = False
try:
    session.append_base64_pcm16("!!!!")
except ValueError:
    checks["stream_strict_base64"] = True
checks["stream_rejects_oversized_frame"] = False
try:
    session.append_pcm16(b"\0" * (main.MAX_ASR_STREAM_FRAME_BYTES + 2))
except ValueError:
    checks["stream_rejects_oversized_frame"] = True
bounded = main.AsrStreamSession(channel="stub-local", sample_rate=16000, chunk_seconds=1)
bounded.append_pcm16(b"\0" * bounded.chunk_bytes * (main.MAX_ASR_STREAM_CHUNKS_PER_RECEIVE + 2))
ready = bounded.pop_ready_wavs(max_chunks=main.MAX_ASR_STREAM_CHUNKS_PER_RECEIVE)
checks["stream_caps_chunks_per_receive"] = len(ready) == main.MAX_ASR_STREAM_CHUNKS_PER_RECEIVE and len(bounded.buffer) >= bounded.chunk_bytes
revision_session = main.AsrStreamSession(channel="stub-local", sample_rate=16000, chunk_seconds=1)
revision_session.append_pcm16(b"\0" * revision_session.chunk_bytes)
revision_one = revision_session.pop_ready_revision_wav()
revision_session.append_pcm16(b"\0" * revision_session.chunk_bytes)
revision_two = revision_session.pop_ready_revision_wav()
checks["stream_revision_uses_full_history"] = (
    revision_one is not None
    and revision_two is not None
    and len(revision_two[1]) > len(revision_one[1])
    and not revision_session.buffer
)
checks["stream_final_revision_uses_full_history"] = bool(revision_session.commit_revision_wav())
checks["stream_uses_bounded_context_windows"] = main.ASR_STREAM_CONTEXT_SECONDS <= 60
long_session = main.AsrStreamSession(
    channel="stub-local",
    sample_rate=8000,
    chunk_seconds=10,
    max_connection_seconds=main.ACCOUNT_ASR_STREAM_SECONDS,
)
one_second = b"\0" * (long_session.sample_rate * 2)
max_history_bytes = 0
rollover_count = 0
for second in range(main.ACCOUNT_ASR_STREAM_SECONDS):
    long_session.append_pcm16(one_second)
    max_history_bytes = max(max_history_bytes, len(long_session.history))
    if (second % 10 == 9):
        long_session.pop_ready_revision_wav()
    if long_session.should_rotate_window:
        long_session.rotate_window()
        rollover_count += 1
checks["stream_simulates_two_hours"] = long_session.total_pcm_bytes == long_session.max_total_bytes
checks["stream_two_hours_has_bounded_memory"] = max_history_bytes <= long_session.context_bytes + len(one_second) * 10
checks["stream_two_hours_rolls_context"] = rollover_count >= 100
checks["stream_rejects_after_account_limit"] = False
try:
    long_session.append_pcm16(one_second)
except ValueError:
    checks["stream_rejects_after_account_limit"] = True
temp_dir = main.PROJECT_ROOT / "playground" / "asr-temp"
temp_dir.mkdir(parents=True, exist_ok=True)
fd, temp_name = tempfile.mkstemp(prefix="qwen-demo-contract-cleanup-", suffix=".wav", dir=str(temp_dir))
os.close(fd)
temp_path = main.Path(temp_name)
main._cleanup_asr_temp_file(temp_path)
checks["stream_temp_cleanup_helper"] = not temp_path.exists()
original_send = main._send_asr_stream_result
try:
    async def failing_send(*args, **kwargs):
        raise RuntimeError("internal diagnostic details should not leak to websocket clients")

    main._send_asr_stream_result = failing_send
    client = TestClient(main.app)
    with client.websocket_connect("/ws/asr/stream") as ws:
        ws.receive_json()
        ws.send_json({"type": "asr.stream.start", "channel": "stub-local", "sample_rate": 16000, "chunk_seconds": 0.5})
        ws.receive_json()
        ws.send_json({"type": "asr.stream.append", "audio": base64.b64encode(b"\0" * 16000).decode()})
        err = ws.receive_json()
        msg = json.dumps(err, ensure_ascii=False)
        checks["stream_generic_errors_are_sanitized"] = err.get("demo_event") == "asr.stream.error" and "stream ASR failed" in err.get("message", "") and "internal diagnostic" not in msg
finally:
    main._send_asr_stream_result = original_send

original_context_seconds = main.ASR_STREAM_CONTEXT_SECONDS
try:
    main.ASR_STREAM_CONTEXT_SECONDS = 1.0
    rollover_client = TestClient(main.app)
    with rollover_client.websocket_connect("/ws/asr/stream") as ws:
        ws.receive_json()
        ws.send_json({"type": "asr.stream.start", "channel": "stub-local", "sample_rate": 8000, "chunk_seconds": 0.5})
        ws.receive_json()
        half_second = base64.b64encode(b"\0" * 8000).decode()
        ws.send_json({"type": "asr.stream.append", "audio": half_second})
        first_revision = ws.receive_json()
        ws.send_json({"type": "asr.stream.append", "audio": half_second})
        final_window_revision = ws.receive_json()
        rollover_done = ws.receive_json()
    checks["stream_auto_rollover_protocol"] = (
        first_revision.get("result", {}).get("stream", {}).get("final") is False
        and final_window_revision.get("result", {}).get("stream", {}).get("final") is True
        and rollover_done.get("final") is False
        and rollover_done.get("rollover") is True
        and rollover_done.get("window_index") == 2
    )
finally:
    main.ASR_STREAM_CONTEXT_SECONDS = original_context_seconds

original_guest_seconds = main.GUEST_ASR_STREAM_SECONDS
try:
    main.GUEST_ASR_STREAM_SECONDS = 1
    limit_client = TestClient(main.app)
    with limit_client.websocket_connect("/ws/asr/stream") as ws:
        limit_ready = ws.receive_json()
        ws.send_json({"type": "asr.stream.start", "channel": "stub-local", "sample_rate": 8000, "chunk_seconds": 0.5})
        ws.receive_json()
        half_second = base64.b64encode(b"\0" * 8000).decode()
        ws.send_json({"type": "asr.stream.append", "audio": half_second})
        ws.receive_json()
        ws.send_json({"type": "asr.stream.append", "audio": half_second})
        ws.receive_json()
        ws.send_json({"type": "asr.stream.append", "audio": half_second})
        limit_final_revision = ws.receive_json()
        limit_done = ws.receive_json()
    checks["stream_limit_finishes_cleanly"] = (
        limit_ready.get("max_connection_seconds") == 1
        and limit_final_revision.get("result", {}).get("stream", {}).get("final") is True
        and limit_done.get("limit_reached") is True
        and limit_done.get("final") is True
    )
finally:
    main.GUEST_ASR_STREAM_SECONDS = original_guest_seconds

client = TestClient(main.app)
with client.websocket_connect("/ws/asr/stream") as ws:
    guest_ready = ws.receive_json()
checks["guest_stream_limit_is_ten_minutes"] = guest_ready.get("max_connection_seconds") == 10 * 60 and guest_ready.get("stream_mode") == "guest"

original_meeting_db_path = main.MEETING_DB_PATH
with tempfile.TemporaryDirectory() as account_directory:
    main.MEETING_DB_PATH = Path(account_directory) / "meetings.sqlite3"
    account_client = TestClient(main.app)
    account_name = f"stream-contract-{os.getpid()}@example.com"
    main.provision_managed_account(account_name, "ContractPass123!")
    logged_in = account_client.post("/api/auth/login", json={"account": account_name, "password": "ContractPass123!"})
    with account_client.websocket_connect("/ws/asr/stream") as ws:
        account_ready = ws.receive_json()
    checks["account_stream_limit_is_two_hours"] = logged_in.status_code == 200 and account_ready.get("max_connection_seconds") == 2 * 60 * 60 and account_ready.get("stream_mode") == "account"
main.MEETING_DB_PATH = original_meeting_db_path

client = TestClient(main.app)
with client.websocket_connect("/ws/asr/stream") as ws:
    ws.receive_json()
    ws.send_json({"type": "attacker-controlled-type-value"})
    err = ws.receive_json()
    checks["stream_unknown_type_not_reflected"] = err.get("demo_event") == "asr.stream.error" and "attacker-controlled" not in json.dumps(err, ensure_ascii=False)
# The stub path must stay available so public smoke can run even if GPU model is warming/downloading.
wav = make_test_wav()
stub = main.transcribe_audio_bytes("stub-local", wav, "asr-gpu-contract-tone.wav", True)
checks["stub_still_available"] = bool(stub.get("board_event") and base64.b64encode(wav))
original_profile = main._read_profile
original_env = os.environ.copy()
try:
    main._read_profile = lambda: {"OPENAI_API_MODEL": "deepseek-v4-pro-0813"}
    checks["meeting_notes_model_prefers_profile"] = main._meeting_notes_model() == "deepseek-v4-pro-0813"
finally:
    main._read_profile = original_profile
    os.environ.clear()
    os.environ.update(original_env)
checks["ok"] = all(bool(v) for k, v in checks.items() if k != "ok")
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if checks["ok"] else 1)
