import io
import wave

import pytest

from chatvoice import __version__


def _tiny_wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 1600)
    return buffer.getvalue()


def test_packaged_web_app_factory_exposes_core_routes(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")

    from chatvoice.web import create_app

    app = create_app()
    paths = {getattr(route, "path", "") for route in app.routes}

    assert app.title == "ChatVoice Speakr"
    assert "/" in paths
    assert "/api/status" in paths
    assert "/api/heartbeat" in paths
    assert "/api/asr/channels" in paths
    assert "/api/asr" in paths
    assert "/api/voice-clone/status" in paths
    assert "/api/voice-clone/jobs" in paths
    assert "/api/voice-clone/jobs/{job_id}" in paths
    assert "/api/voice-clone/jobs/{job_id}/audio" in paths
    assert "/api/tokens" in paths
    assert "/api/tokens/{token_id}" in paths
    assert "/api/data/meetings" in paths
    assert "/api/data/meetings/{meeting_id}" in paths
    assert "/api/data/conversations" in paths
    assert "/api/data/conversations/{conversation_id}" in paths


def test_status_exposes_sanitized_server_side_api_key_configuration(monkeypatch, tmp_path):
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "api-server")
    monkeypatch.setenv("CHATVOICE_ASR_API_URL", "https://asr.example.test/v1/transcribe")
    monkeypatch.setenv("CHATVOICE_ASR_API_KEY", "secret-asr-key")
    monkeypatch.setenv("CHATVOICE_OPENAI_API_BASE", "https://token-plan.example.test/compatible-mode/v1")
    monkeypatch.setenv("CHATVOICE_OPENAI_API_KEY", "sk-sp-test-token-plan-key")
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        response = TestClient(legacy_app.app).get("/api/status")
        payload = response.json()

        assert response.status_code == 200
        assert payload["api_keys"] == {
            "asr_api_key_configured": True,
            "model_api_key_configured": True,
            "model_api_key_is_token_plan": True,
            "voice_cloning_key_configured": False,
        }
        assert payload["asr_api"]["url_configured"] is True
        assert payload["asr_api"]["endpoint_host"] == "asr.example.test"
        assert payload["asr_api"]["api_key_configured"] is True
        assert "secret-asr-key" not in response.text
        assert "sk-sp-test-token-plan-key" not in response.text
    finally:
        sys.modules.pop(module_name, None)


def test_tts_returns_503_without_model_key_instead_of_500(monkeypatch, tmp_path):
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")
    monkeypatch.delenv("CHATVOICE_OPENAI_API_KEY", raising=False)
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        response = TestClient(legacy_app.app).post("/api/tts", json={"text": "测试", "voice": "longanlingxin", "format": "mp3"})
        assert response.status_code == 503
        assert "CHATVOICE_OPENAI_API_KEY" in response.json()["detail"]
    finally:
        sys.modules.pop(module_name, None)


def test_tts_rejects_usage_billed_openai_key(monkeypatch, tmp_path):
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")
    monkeypatch.setenv("CHATVOICE_OPENAI_API_KEY", "sk-usage-billed-key")
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        response = TestClient(legacy_app.app).post("/api/tts", json={"text": "测试", "voice": "longanlingxin", "format": "mp3"})
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert "sk-sp" in detail
        assert "避免按量扣费" in detail
        assert "sk-usage-billed-key" not in response.text
    finally:
        sys.modules.pop(module_name, None)


def test_status_reads_token_plan_key_from_chatenv_chatvoice_profile(monkeypatch, tmp_path):
    import importlib
    import sys

    from chatenv import EnvStore, get_paths

    from chatvoice.config import ChatVoiceConfig

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.delenv("CHATVOICE_OPENAI_API_KEY", raising=False)
    store = EnvStore(get_paths(tmp_path / "chatarch-home").envs_dir)
    store.save_active(
        ChatVoiceConfig,
        {
            "CHATVOICE_OPENAI_API_BASE": "https://token-plan.example.test/compatible-mode/v1",
            "CHATVOICE_OPENAI_API_KEY": "sk-sp-from-chatenv-profile",
            "CHATVOICE_OPENAI_API_MODEL": "qwen3.7-plus",
        },
    )
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        payload = TestClient(legacy_app.app).get("/api/status").json()
        assert payload["profile"] == "ChatEnv ChatVoice active profile + process env override"
        assert payload["chatenv_storage"] == "ChatVoice"
        assert payload["api_keys"]["model_api_key_configured"] is True
        assert payload["api_keys"]["model_api_key_is_token_plan"] is True
        assert "sk-sp-from-chatenv-profile" not in str(payload)
    finally:
        sys.modules.pop(module_name, None)


def test_heartbeat_exposes_asr_health_without_secret_values(monkeypatch, tmp_path):
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "chatvoice-home"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")
    (tmp_path / "chatvoice-home" / "data").mkdir(parents=True)
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        client = TestClient(legacy_app.app)
        response = client.get("/api/heartbeat")
        payload = response.json()

        assert response.status_code == 200
        assert payload["ok"] is True
        assert payload["service"] == "chatvoice"
        assert payload["version"] == __version__
        assert payload["database"]["ok"] is True
        assert payload["asr"]["default_channel"] == "stub-local"
        assert payload["asr"]["status"] == "ready"
    finally:
        sys.modules.pop(module_name, None)


def test_funasr_gpu_requires_persistent_model_by_default(monkeypatch, tmp_path):
    """Do not silently fall back to a short-lived worker that reloads GPU ASR per chunk."""
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "chatvoice-home"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "funasr-gpu")
    monkeypatch.delenv("CHATVOICE_FUNASR_ALLOW_SUBPROCESS_WORKER", raising=False)
    fake_worker_python = tmp_path / "asr-venv" / "bin" / "python"
    fake_worker_python.parent.mkdir(parents=True)
    fake_worker_python.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    monkeypatch.setenv("ASR_GPU_VENV", str(tmp_path / "asr-venv"))
    (tmp_path / "chatvoice-home" / "data").mkdir(parents=True)
    try:
        legacy_app = importlib.import_module(module_name)

        def fail_in_process(*_args, **_kwargs):
            raise ImportError("funasr missing from service venv")

        def forbidden_subprocess(*_args, **_kwargs):
            raise AssertionError("short-lived FunASR subprocess worker was spawned")

        monkeypatch.setattr(legacy_app, "_get_cached_funasr_model", fail_in_process)
        monkeypatch.setattr(legacy_app.subprocess, "run", forbidden_subprocess)

        with pytest.raises(RuntimeError) as exc_info:
            legacy_app._funasr_asr(_tiny_wav_bytes(), "coldstart.wav", "funasr-gpu", "cuda:0")

        message = str(exc_info.value)
        assert "persistent" in message.lower()
        assert "CHATVOICE_FUNASR_ALLOW_SUBPROCESS_WORKER" in message
    finally:
        sys.modules.pop(module_name, None)


def test_startup_prewarms_default_funasr_gpu_model(monkeypatch, tmp_path):
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "chatvoice-home"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "funasr-gpu")
    monkeypatch.delenv("CHATVOICE_ASR_PREWARM", raising=False)
    (tmp_path / "chatvoice-home" / "data").mkdir(parents=True)
    try:
        legacy_app = importlib.import_module(module_name)
        calls = []

        def fake_get_cached(model_name, device):
            calls.append((model_name, device))
            return object(), object()

        monkeypatch.setattr(legacy_app, "_get_cached_funasr_model", fake_get_cached)
        legacy_app._prewarm_asr_if_configured()

        assert calls == [(legacy_app.FUNASR_MODEL, legacy_app.FUNASR_GPU_DEVICE)]
    finally:
        sys.modules.pop(module_name, None)


def test_voice_clone_status_reports_not_configured_without_secret_values(monkeypatch, tmp_path):
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "chatvoice-home"))
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.delenv("CHATVOICE_VOICECLONE_URL", raising=False)
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        response = TestClient(legacy_app.app).get("/api/voice-clone/status")
        payload = response.json()

        assert response.status_code == 200
        assert payload["configured"] is False
        assert payload["status"] == "not-configured"
        assert payload["mode"] == "local-one-shot-sidecar"
    finally:
        sys.modules.pop(module_name, None)


def test_voice_clone_status_proxies_local_sidecar_without_secret_values(monkeypatch, tmp_path):
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "chatvoice-home"))
    monkeypatch.setenv("CHATVOICE_VOICECLONE_URL", "http://127.0.0.1:18187")
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        def fake_get_json(path):
            assert path == "/health"
            return {"ok": True, "engine": "indextts", "provider": "indextts-local", "device": "cuda:0"}

        monkeypatch.setattr(legacy_app, "_voiceclone_get_json", fake_get_json)
        response = TestClient(legacy_app.app).get("/api/voice-clone/status")
        payload = response.json()

        assert response.status_code == 200
        assert payload["configured"] is True
        assert payload["status"] == "ready"
        assert payload["engine"] == "indextts"
        assert "127.0.0.1:18187" not in response.text
    finally:
        sys.modules.pop(module_name, None)


def test_voice_clone_create_job_requires_login(monkeypatch, tmp_path):
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "chatvoice-home"))
    monkeypatch.setenv("CHATVOICE_VOICECLONE_URL", "http://127.0.0.1:18187")
    (tmp_path / "chatvoice-home" / "data").mkdir(parents=True)
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        response = TestClient(legacy_app.app).post(
            "/api/voice-clone/jobs",
            data={"text": "hello", "lang": "en"},
            files={"reference_audio": ("reference.wav", b"RIFF....WAVE", "audio/wav")},
        )

        assert response.status_code == 401
    finally:
        sys.modules.pop(module_name, None)


def test_asr_upload_updates_heartbeat_recent_success(monkeypatch, tmp_path):
    import importlib
    import io
    import sys
    import wave

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "chatvoice-home"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")
    (tmp_path / "chatvoice-home" / "data").mkdir(parents=True)
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        client = TestClient(legacy_app.app)
        audio = io.BytesIO()
        with wave.open(audio, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x00\x00" * 800)

        response = client.post(
            "/api/asr",
            data={"channel": "stub-local", "correct": "true"},
            files={"file": ("smoke.wav", audio.getvalue(), "audio/wav")},
        )
        assert response.status_code == 200

        heartbeat = client.get("/api/heartbeat").json()
        recent = heartbeat["asr"]["recent"]
        assert heartbeat["asr"]["status"] == "ready"
        assert recent["last_channel"] == "stub-local"
        assert recent["last_success_at"]
        assert recent["last_text_chars"] > 0
        assert recent["last_error_type"] is None
    finally:
        sys.modules.pop(module_name, None)


class _FakeSseResponse:
    def __init__(self, events):
        self._events = events

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        for event in self._events:
            yield b"data: " + event + b"\n\n"


def _save_openai_profile(tmp_path, name="apple", base="https://crs.example.wzhecnu.cn/openai/v1", model="gpt-stable"):
    from chatenv import EnvStore, OpenAIConfig, get_paths

    home = tmp_path / "chatarch-home"
    store = EnvStore(get_paths(home).envs_dir)
    store.save_profile(OpenAIConfig, name, {"OPENAI_API_BASE": base, "OPENAI_API_KEY": "cr_secret", "OPENAI_API_MODEL": model})
    return home


def test_meeting_notes_can_use_crs_chat_completions_profile_without_reusing_token_plan(monkeypatch, tmp_path):
    import importlib
    import json
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    home = _save_openai_profile(tmp_path)
    monkeypatch.setenv("CHATARCH_HOME", str(home))
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "chatvoice-home"))
    monkeypatch.setenv("CHATVOICE_MEETING_NOTES_PROVIDER", "crs-chat-completions")
    monkeypatch.setenv("CHATVOICE_MEETING_NOTES_CRS_PROFILE", "apple")
    monkeypatch.setenv("CHATVOICE_OPENAI_API_KEY", "sk-sp-token-plan-notes-should-not-use")
    try:
        legacy_app = importlib.import_module(module_name)
        calls = []

        def fake_urlopen(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            calls.append((request.full_url, request.get_header("Authorization"), body, timeout))
            events = [
                json.dumps({"choices": [{"delta": {"content": "稳定"}}]}).encode("utf-8"),
                json.dumps({"choices": [{"delta": {"content": "纪要"}}]}).encode("utf-8"),
                json.dumps({"usage": {"output_tokens": 2}, "choices": [{"delta": {}}]}).encode("utf-8"),
            ]
            return _FakeSseResponse(events)

        monkeypatch.setattr(legacy_app.urllib.request, "urlopen", fake_urlopen)
        result = legacy_app._meeting_notes_blocking(legacy_app.MeetingNotesRequest(transcript="会议讨论稳定模型", instruction="输出纪要"))

        assert result["provider"] == "crs-chat-completions"
        assert result["model"] == "gpt-stable"
        assert result["content"] == "稳定纪要"
        assert legacy_app._meeting_notes_status() == {
            "provider": "crs-chat-completions",
            "model": "gpt-stable",
            "crs_profile": "apple",
            "base_host": "crs.example.wzhecnu.cn",
            "key_configured": True,
        }
        assert calls == [
            (
                "https://crs.example.wzhecnu.cn/openai/v1/chat/completions",
                "Bearer cr_secret",
                {
                    "model": "gpt-stable",
                    "messages": [
                        {"role": "system", "content": "你是会议纪要实时整理助手，只输出中文结构化结果。"},
                        {"role": "user", "content": "输出纪要\n\n转写文本：\n会议讨论稳定模型"},
                    ],
                    "stream": True,
                },
                80,
            )
        ]
    finally:
        sys.modules.pop(module_name, None)


def test_meeting_notes_crs_provider_refuses_non_crs_profile_base(monkeypatch, tmp_path):
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    home = _save_openai_profile(tmp_path, base="https://poison.example.test/v1")
    monkeypatch.setenv("CHATARCH_HOME", str(home))
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "chatvoice-home"))
    monkeypatch.setenv("CHATVOICE_MEETING_NOTES_PROVIDER", "crs-responses")
    monkeypatch.setenv("CHATVOICE_MEETING_NOTES_CRS_PROFILE", "apple")
    try:
        legacy_app = importlib.import_module(module_name)
        with pytest.raises(legacy_app.HTTPException) as exc_info:
            legacy_app._meeting_notes_blocking(legacy_app.MeetingNotesRequest(transcript="会议", instruction="输出纪要"))
        assert exc_info.value.status_code == 503
        assert "non-CRS" in str(exc_info.value.detail)
    finally:
        sys.modules.pop(module_name, None)


def test_meeting_notes_revision_stream_can_use_crs_chat_completions(monkeypatch, tmp_path):
    import importlib
    import json
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    home = _save_openai_profile(tmp_path)
    monkeypatch.setenv("CHATARCH_HOME", str(home))
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "chatvoice-home"))
    monkeypatch.setenv("CHATVOICE_MEETING_NOTES_PROVIDER", "crs-chat-completions")
    monkeypatch.setenv("CHATVOICE_MEETING_NOTES_CRS_PROFILE", "apple")
    try:
        legacy_app = importlib.import_module(module_name)

        def fake_urlopen(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            assert request.full_url == "https://crs.example.wzhecnu.cn/openai/v1/chat/completions"
            assert body["stream"] is True
            assert body["model"] == "gpt-stable"
            return _FakeSseResponse([
                json.dumps({"choices": [{"delta": {"content": "新纪要"}}]}).encode("utf-8"),
                json.dumps({"usage": {"output_tokens": 3}, "choices": [{"delta": {}}]}).encode("utf-8"),
            ])

        monkeypatch.setattr(legacy_app.urllib.request, "urlopen", fake_urlopen)
        events = "".join(
            legacy_app._meeting_notes_revision_stream(
                legacy_app.MeetingNotesReviseRequest(transcript="会议", current_summary="旧纪要", instruction="润色")
            )
        )

        assert '"provider": "crs-chat-completions"' in events
        assert "新纪要" in events
        assert "event: done" in events
    finally:
        sys.modules.pop(module_name, None)
