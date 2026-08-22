from chatvoice import __version__


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
    monkeypatch.setenv("OPENAI_API_BASE", "https://token-plan.example.test/compatible-mode/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sp-test-token-plan-key")
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
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        response = TestClient(legacy_app.app).post("/api/tts", json={"text": "测试", "voice": "longanlingxin", "format": "mp3"})
        assert response.status_code == 503
        assert "OPENAI_API_KEY" in response.json()["detail"]
    finally:
        sys.modules.pop(module_name, None)


def test_tts_rejects_usage_billed_openai_key(monkeypatch, tmp_path):
    import importlib
    import sys

    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-usage-billed-key")
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
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = EnvStore(get_paths(tmp_path / "chatarch-home").envs_dir)
    store.save_active(
        ChatVoiceConfig,
        {
            "OPENAI_API_BASE": "https://token-plan.example.test/compatible-mode/v1",
            "OPENAI_API_KEY": "sk-sp-from-chatenv-profile",
            "OPENAI_API_MODEL": "qwen3.7-plus",
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
