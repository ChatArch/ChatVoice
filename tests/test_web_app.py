def test_packaged_web_app_factory_exposes_core_routes(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")

    from chatvoice.web import create_app

    app = create_app()
    paths = {getattr(route, "path", "") for route in app.routes}

    assert app.title == "ChatVoice Speakr"
    assert "/" in paths
    assert "/api/status" in paths
    assert "/api/asr/channels" in paths
    assert "/api/asr" in paths
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
    monkeypatch.setenv("DASHSCOPE_API_KEY", "secret-model-key")
    try:
        legacy_app = importlib.import_module(module_name)
        from fastapi.testclient import TestClient

        response = TestClient(legacy_app.app).get("/api/status")
        payload = response.json()

        assert response.status_code == 200
        assert payload["api_keys"] == {
            "asr_api_key_configured": True,
            "model_api_key_configured": True,
            "voice_cloning_key_configured": True,
        }
        assert payload["asr_api"]["url_configured"] is True
        assert payload["asr_api"]["endpoint_host"] == "asr.example.test"
        assert payload["asr_api"]["api_key_configured"] is True
        assert "secret-asr-key" not in response.text
        assert "secret-model-key" not in response.text
    finally:
        sys.modules.pop(module_name, None)
