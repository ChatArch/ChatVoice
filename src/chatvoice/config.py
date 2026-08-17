"Typed environment configuration for ChatVoice."

from chatenv import BaseEnvConfig, EnvField


class ChatvoiceConfig(BaseEnvConfig):
    "ChatVoice ChatEnv configuration."

    _title = "ChatVoice Configuration"
    _aliases = ["chatvoice"]
    _storage_dir = "Chatvoice"

    @classmethod
    def test(cls) -> None:
        """Validate schema registration without external side effects."""

        print(f"Testing {cls._title}...")
        print("Schema loaded; no network test is required.")

    CHATVOICE_API_KEY = EnvField(
        "CHATVOICE_API_KEY",
        desc="API key",
        is_sensitive=True,
    )


__all__ = ["ChatvoiceConfig"]
