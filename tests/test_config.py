from importlib.metadata import entry_points

from chatenv import EnvStore, get_paths

from chatvoice.config import ChatvoiceConfig


def test_chatenv_provider_entry_point_loads_typed_config():
    providers = {
        entry_point.name: entry_point
        for entry_point in entry_points(group="chatenv.configs")
    }

    assert providers["chatvoice"].value == "chatvoice.config"
    assert providers["chatvoice"].load().ChatvoiceConfig is ChatvoiceConfig


def test_config_marks_credentials_and_database_url_sensitive():
    fields = ChatvoiceConfig.get_fields()

    for name in (
        "CHATVOICE_ASR_API_KEY",
        "CHATVOICE_DATABASE_URL",
        "QWEN_TOKEN_PLAN_ENV_FILE",
        "DASHSCOPE_API_KEY",
        "OPENAI_API_KEY",
    ):
        assert fields[name].is_sensitive is True


def test_config_uses_chatenv_profile_storage_paths(tmp_path):
    store = EnvStore(get_paths(tmp_path).envs_dir)

    assert store.active_path(ChatvoiceConfig) == (
        tmp_path / "envs" / "Chatvoice" / ".env"
    )
    assert store.profile_path(ChatvoiceConfig, "example") == (
        tmp_path / "envs" / "Chatvoice" / "example.env"
    )
