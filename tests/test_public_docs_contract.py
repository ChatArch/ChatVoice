"""Public docs preserve contracts without duplicating every detail on every page."""
from pathlib import Path
import re
from chatvoice import __version__

ROOT = Path(__file__).resolve().parents[1]

def text(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_public_fresh_install_examples_track_package_version():
    for name in ("README.md", "README.en.md", "docs/quickstart.md", "docs/quickstart.en.md", "docs/deployment.md", "docs/deployment.en.md"):
        assert f'python -m pip install "ChatVoice[web]=={__version__}"' in text(name), name
    for path in (ROOT / "docs").glob("*.md"):
        versions = re.findall(r"ChatVoice\[web\]==([\d.]+)", path.read_text())
        assert all(version == __version__ for version in versions), path


def test_public_docs_use_executable_asr_api_url_setting_name():
    for name in ("docs/quickstart.md", "docs/quickstart.en.md", "docs/configuration.md", "docs/configuration.en.md", "docs/deployment.md", "docs/deployment.en.md"):
        assert "CHATVOICE_ASR_API_URL" in text(name), name
        assert "<ASR_API_URL_SETTING>" not in text(name)


def test_summary_boundary_respects_each_document_language():
    for name in ("README.md", "docs/deployment.md"):
        assert "摘要" in text(name) and "服务端" in text(name), name
    for name in ("README.en.md", "docs/deployment.en.md"):
        assert "summary" in text(name).lower() and "server-side" in text(name).lower(), name
    for name in ("docs/configuration.md", "docs/configuration.en.md"):
        assert "CHATVOICE_MEETING_NOTES_API_KEY" in text(name)
        assert "CHATVOICE_MEETING_TITLE_API_KEY" in text(name)


def test_runtime_details_live_on_the_linked_runtime_reference():
    required = ("site-packages", "~/.chatarch/chatvoice", "CHATVOICE_HOME", "CHATARCH_HOME", "meetings.sqlite3", "accounts", "api_tokens", "meeting_records", "conversation_records", "temp/asr", "model-cache", "Postgres/MySQL")
    for name in ("docs/runtime-layout.md", "docs/runtime-layout.en.md"):
        assert all(fragment in text(name) for fragment in required), name
    for name in ("README.md", "README.en.md", "docs/deployment.md", "docs/deployment.en.md"):
        assert "runtime-layout" in text(name), name
