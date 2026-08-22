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
        "CHATVOICE_DATABASE_URL",
        "OPENAI_API_KEY",
    ):
        assert fields[name].is_sensitive is True

    assert "QWEN_TOKEN_PLAN_ENV_FILE" not in fields
    assert "DASHSCOPE_API_KEY" not in fields
    assert "DASHSCOPE_VOICE_API_KEY" not in fields
    assert "OPENAI_API_BASE" in fields
    assert "OPENAI_API_MODEL" in fields
    assert "CHATVOICE_MEETING_NOTES_MODEL" in fields
    assert "CHATVOICE_MEETING_TITLE_MODEL" in fields
    assert "CHATVOICE_REALTIME_MODELS" in fields
    assert fields["OPENAI_API_MODEL"].default == "qwen3.7-plus"


def test_config_uses_canonical_chatenv_profile_storage_paths(tmp_path):
    store = EnvStore(get_paths(tmp_path).envs_dir)

    assert store.active_path(ChatVoiceConfig) == (
        tmp_path / "envs" / "ChatVoice" / ".env"
    )
    assert store.profile_path(ChatVoiceConfig, "example") == (
        tmp_path / "envs" / "ChatVoice" / "example.env"
    )
