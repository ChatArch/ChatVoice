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

    CHATVOICE_ASR_CHANNEL = EnvField(
        "CHATVOICE_ASR_CHANNEL",
        desc="ASR provider channel, usually api-server or stub-local",
    )
    CHATVOICE_ASR_API_URL = EnvField(
        "CHATVOICE_ASR_API_URL",
        desc="HTTP endpoint for managed or self-hosted ASR API server",
    )
    CHATVOICE_ASR_API_KEY = EnvField(
        "CHATVOICE_ASR_API_KEY",
        desc="Optional ASR API bearer token",
        is_sensitive=True,
    )
    CHATVOICE_DATABASE_URL = EnvField(
        "CHATVOICE_DATABASE_URL",
        desc="Database URL. v0.1.5 packaged web storage supports SQLite only; external DB is detected for migration planning.",
        is_sensitive=True,
    )
    CHATVOICE_HOME = EnvField(
        "CHATVOICE_HOME",
        desc="Override ChatVoice runtime root. Defaults to $CHATARCH_HOME/chatvoice or ~/.chatarch/chatvoice.",
    )
    QWEN_TOKEN_PLAN_ENV_FILE = EnvField(
        "QWEN_TOKEN_PLAN_ENV_FILE",
        desc="Optional local server-side env file for Qwen-compatible provider keys",
        is_sensitive=True,
    )
    DASHSCOPE_API_KEY = EnvField(
        "DASHSCOPE_API_KEY",
        desc="Server-side DashScope/Qwen API key for TTS, notes, and realtime proxy",
        is_sensitive=True,
    )
    OPENAI_API_KEY = EnvField(
        "OPENAI_API_KEY",
        desc="Server-side OpenAI-compatible API key fallback for Qwen-compatible calls",
        is_sensitive=True,
    )


__all__ = ["ChatvoiceConfig"]
