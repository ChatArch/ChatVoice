"Typed ChatEnv configuration for ChatVoice."

from chatenv import BaseEnvConfig, EnvField


class ChatVoiceConfig(BaseEnvConfig):
    """ChatVoice ChatEnv configuration.

    ChatVoice uses ChatEnv as the single durable configuration surface.
    Model-provider settings intentionally use service-scoped OpenAI-compatible
    names (`CHATVOICE_OPENAI_API_BASE`, `CHATVOICE_OPENAI_API_KEY`,
    `CHATVOICE_OPENAI_API_MODEL`) so they do not overlap with ChatEnv
    built-in OpenAI provider profiles.
    """

    _title = "ChatVoice Configuration"
    _aliases = ["chatvoice"]
    _storage_dir = "ChatVoice"

    @classmethod
    def test(cls) -> None:
        """Probe explicit text endpoints; legacy profiles remain schema-only."""

        from click import get_current_context
        from chatenv import EnvStore
        from chatvoice.text_api import probe_text_configuration

        # ChatEnv 0.2.x dispatches test() without loading the selected profile.
        # Reuse its already-resolved store (including --home), not a second parser.
        context = get_current_context(silent=True)
        root_values = context.find_root().obj if context is not None else None
        store = root_values.get("store") if isinstance(root_values, dict) else None
        if isinstance(store, EnvStore):
            cls.load_from_sources(env_values=store.load_active(cls))

        print(f"Testing {cls._title}...")
        results = probe_text_configuration({field.env_key: field.value for field in cls.get_fields().values()})
        if not results:
            print("Schema loaded; no independent text endpoint configured (no network test).")
        for purpose in results:
            print(f"Meeting {purpose}: synthetic connectivity test passed.")

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
    CHATVOICE_ASR_PREWARM = EnvField(
        "CHATVOICE_ASR_PREWARM",
        default="1",
        desc="Preload persistent FunASR model during service startup when a FunASR channel is selected.",
    )
    CHATVOICE_FUNASR_ALLOW_SUBPROCESS_WORKER = EnvField(
        "CHATVOICE_FUNASR_ALLOW_SUBPROCESS_WORKER",
        default="0",
        desc="Compatibility/debug only: allow short-lived FunASR subprocess workers that reload models per request. Keep disabled in production.",
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
    CHATVOICE_MEETING_NOTES_PROVIDER = EnvField(
        "CHATVOICE_MEETING_NOTES_PROVIDER",
        default="token-plan-chat-completions",
        desc="Meeting-notes backend: token-plan-chat-completions, crs-chat-completions, or crs-responses.",
    )
    CHATVOICE_MEETING_NOTES_CRS_PROFILE = EnvField(
        "CHATVOICE_MEETING_NOTES_CRS_PROFILE",
        desc="ChatEnv OpenAI profile name for CRS-backed meeting notes, for example apple.",
    )
    CHATVOICE_MEETING_NOTES_CRS_API_BASE = EnvField(
        "CHATVOICE_MEETING_NOTES_CRS_API_BASE",
        desc="Explicit CRS Responses API base URL. Prefer CHATVOICE_MEETING_NOTES_CRS_PROFILE.",
    )
    CHATVOICE_MEETING_NOTES_CRS_API_KEY = EnvField(
        "CHATVOICE_MEETING_NOTES_CRS_API_KEY",
        desc="Explicit CRS API key for meeting notes. Prefer CHATVOICE_MEETING_NOTES_CRS_PROFILE.",
        is_sensitive=True,
    )
    CHATVOICE_MEETING_NOTES_API_BASE = EnvField(
        "CHATVOICE_MEETING_NOTES_API_BASE",
        desc="Independent meeting-notes chat/completions base; requires its own API key and model.",
    )
    CHATVOICE_MEETING_NOTES_API_KEY = EnvField(
        "CHATVOICE_MEETING_NOTES_API_KEY",
        desc="Independent meeting-notes API key; never borrowed from voice, CRS or global OpenAI.",
        is_sensitive=True,
    )
    CHATVOICE_MEETING_TITLE_API_BASE = EnvField(
        "CHATVOICE_MEETING_TITLE_API_BASE",
        desc="Independent meeting-title chat/completions base; requires its own API key and model.",
    )
    CHATVOICE_MEETING_TITLE_API_KEY = EnvField(
        "CHATVOICE_MEETING_TITLE_API_KEY",
        desc="Independent meeting-title API key; never borrowed from voice, CRS or global OpenAI.",
        is_sensitive=True,
    )
    CHATVOICE_MEETING_NOTES_MODEL = EnvField(
        "CHATVOICE_MEETING_NOTES_MODEL",
        desc="Required for independent meeting notes; otherwise defaults to legacy provider profile or CHATVOICE_OPENAI_API_MODEL.",
    )
    CHATVOICE_MEETING_TITLE_MODEL = EnvField(
        "CHATVOICE_MEETING_TITLE_MODEL",
        desc="Required for independent meeting titles; otherwise defaults to CHATVOICE_OPENAI_API_MODEL.",
    )
    CHATVOICE_REALTIME_MODELS = EnvField(
        "CHATVOICE_REALTIME_MODELS",
        desc="Optional comma-separated allowlist for realtime audio models.",
    )
    CHATVOICE_OPENAI_API_BASE = EnvField(
        "CHATVOICE_OPENAI_API_BASE",
        default="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        desc="ChatVoice-scoped OpenAI-compatible model API base URL. Token Plan deployments use this OpenAI-compatible base.",
    )
    CHATVOICE_OPENAI_API_KEY = EnvField(
        "CHATVOICE_OPENAI_API_KEY",
        desc="ChatVoice-scoped OpenAI-compatible model API key. ChatVoice production accepts Token Plan sk-sp keys by default.",
        is_sensitive=True,
    )
    CHATVOICE_OPENAI_API_MODEL = EnvField(
        "CHATVOICE_OPENAI_API_MODEL",
        default="qwen3.7-plus",
        desc="Default ChatVoice-scoped OpenAI-compatible model for text/model-backed tasks.",
    )


# Backwards-compatible class name for imports/tests from earlier releases.
ChatvoiceConfig = ChatVoiceConfig

__all__ = ["ChatVoiceConfig", "ChatvoiceConfig"]
