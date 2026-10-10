from importlib.metadata import entry_points

from chatenv import EnvStore, get_paths

from chatvoice.config import ChatVoiceConfig, ChatvoiceConfig


def test_chatenv_provider_entry_point_loads_typed_config():
    providers = {
        entry_point.name: entry_point
        for entry_point in entry_points(group="chatenv.configs")
    }

    assert providers["chatvoice"].value == "chatvoice.config"
    loaded = providers["chatvoice"].load()
    assert loaded.ChatVoiceConfig is ChatVoiceConfig
    assert loaded.ChatvoiceConfig is ChatvoiceConfig
    assert ChatvoiceConfig is ChatVoiceConfig


def test_config_marks_credentials_and_database_url_sensitive():
    fields = ChatVoiceConfig.get_fields()

    for name in (
        "CHATVOICE_ASR_API_KEY",
        "CHATVOICE_OPENAI_API_KEY",
        "CHATVOICE_MEETING_NOTES_CRS_API_KEY",
    ):
        assert fields[name].is_sensitive is True

    assert "QWEN_TOKEN_PLAN_ENV_FILE" not in fields
    assert "DASHSCOPE_API_KEY" not in fields
    assert "DASHSCOPE_VOICE_API_KEY" not in fields
    assert "CHATVOICE_DATABASE_URL" not in fields
    assert "OPENAI_API_BASE" not in fields
    assert "OPENAI_API_KEY" not in fields
    assert "OPENAI_API_MODEL" not in fields
    assert "CHATVOICE_OPENAI_API_BASE" in fields
    assert "CHATVOICE_OPENAI_API_KEY" in fields
    assert "CHATVOICE_OPENAI_API_MODEL" in fields
    assert "CHATVOICE_PUBLIC_ORIGIN" in fields
    assert fields["CHATVOICE_PUBLIC_ORIGIN"].default == "http://127.0.0.1:18087"
    assert "CHATVOICE_MEETING_NOTES_PROVIDER" in fields
    assert "CHATVOICE_MEETING_NOTES_CRS_PROFILE" in fields
    assert "CHATVOICE_MEETING_NOTES_CRS_API_BASE" in fields
    assert "CHATVOICE_MEETING_NOTES_CRS_API_KEY" in fields
    assert "CHATVOICE_MEETING_NOTES_MODEL" in fields
    assert "CHATVOICE_MEETING_TITLE_MODEL" in fields
    assert "CHATVOICE_REALTIME_MODELS" in fields
    assert fields["CHATVOICE_MEETING_NOTES_PROVIDER"].default == "token-plan-chat-completions"
    assert fields["CHATVOICE_OPENAI_API_MODEL"].default == "qwen3.7-plus"


def test_config_uses_canonical_chatenv_profile_storage_paths(tmp_path):
    store = EnvStore(get_paths(tmp_path).envs_dir)

    assert store.active_path(ChatVoiceConfig) == (
        tmp_path / "envs" / "ChatVoice" / ".env"
    )
    assert store.profile_path(ChatVoiceConfig, "example") == (
        tmp_path / "envs" / "ChatVoice" / "example.env"
    )


def test_public_origin_validation_rejects_untrusted_shapes():
    from chatvoice.web.user_management import validate_public_origin

    assert validate_public_origin("https://speakr.example.test") == "https://speakr.example.test"
    assert validate_public_origin("http://127.0.0.1:18087/") == "http://127.0.0.1:18087"
    for value in (
        "https://user@speakr.example.test",
        "https://speakr.example.test/path",
        "https://speakr.example.test?x=1",
        "https://speakr.example.test#frag",
        "http://127.0.0.1:99999",
        "ftp://speakr.example.test",
        "https://speakr.example.test bad",
    ):
        try:
            validate_public_origin(value)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"origin accepted unexpectedly: {value}")
