"Typed ChatEnv configuration for ChatVoice."

from chatenv import BaseEnvConfig, EnvField


class ChatVoiceConfig(BaseEnvConfig):
    """ChatVoice ChatEnv configuration.

    ChatVoice uses ChatEnv as the single durable configuration surface.
    Model-provider settings intentionally use the OpenAI-compatible names
    (`OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_API_MODEL`) so deployment
    does not invent a parallel Qwen/DashScope env system.
    """

    _title = "ChatVoice Configuration"
    _aliases = ["chatvoice"]
    _storage_dir = "ChatVoice"

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
        desc="Database URL. Packaged web storage currently supports SQLite only; external DB is detected for migration planning.",
        is_sensitive=True,
    )
    CHATVOICE_HOME = EnvField(
        "CHATVOICE_HOME",
        desc="Override ChatVoice runtime root. Defaults to $CHATARCH_HOME/chatvoice or ~/.chatarch/chatvoice.",
    )
    CHATVOICE_SQLITE_PATH = EnvField(
        "CHATVOICE_SQLITE_PATH",
        desc="Optional explicit SQLite database path under the ChatVoice runtime root.",
    )
    CHATVOICE_VOICECLONE_URL = EnvField(
        "CHATVOICE_VOICECLONE_URL",
        desc="Local VoiceClone sidecar base URL for one-shot voice cloning.",
    )
    CHATVOICE_VOICECLONE_TIMEOUT_SECONDS = EnvField(
        "CHATVOICE_VOICECLONE_TIMEOUT_SECONDS",
        default="180",
        desc="VoiceClone sidecar request timeout in seconds.",
    )
    CHATVOICE_MEETING_NOTES_MODEL = EnvField(
        "CHATVOICE_MEETING_NOTES_MODEL",
        desc="Optional override for meeting-notes generation; defaults to OPENAI_API_MODEL.",
    )
    CHATVOICE_MEETING_TITLE_MODEL = EnvField(
        "CHATVOICE_MEETING_TITLE_MODEL",
        desc="Optional override for meeting-title generation; defaults to OPENAI_API_MODEL.",
    )
    CHATVOICE_REALTIME_MODELS = EnvField(
        "CHATVOICE_REALTIME_MODELS",
        desc="Optional comma-separated allowlist for realtime audio models.",
    )
    OPENAI_API_BASE = EnvField(
        "OPENAI_API_BASE",
        default="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        desc="OpenAI-compatible model API base URL. Token Plan deployments use this OpenAI-compatible base.",
    )
    OPENAI_API_KEY = EnvField(
        "OPENAI_API_KEY",
        desc="OpenAI-compatible model API key. ChatVoice production accepts Token Plan sk-sp keys by default.",
        is_sensitive=True,
    )
    OPENAI_API_MODEL = EnvField(
        "OPENAI_API_MODEL",
        default="qwen3.7-plus",
        desc="Default OpenAI-compatible model for text/model-backed tasks.",
    )


# Backwards-compatible class name for imports/tests from earlier releases.
ChatvoiceConfig = ChatVoiceConfig

__all__ = ["ChatVoiceConfig", "ChatvoiceConfig"]
