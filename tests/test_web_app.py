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
