from pathlib import Path

from chatvoice import __version__


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DOCS = [
    ROOT / "README.md",
    ROOT / "README.en.md",
    ROOT / "docs" / "deployment.md",
    ROOT / "docs" / "deployment.en.md",
    ROOT / "docs" / "api-access.md",
    ROOT / "docs" / "api-access.en.md",
    ROOT / "docs" / "index.md",
    ROOT / "docs" / "index.en.md",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_fresh_install_examples_track_package_version():
    install_snippet = f'python -m pip install "ChatVoice[web]=={__version__}"'
    for path in PUBLIC_DOCS:
        text = _read(path)
        assert "ChatVoice[web]==0.1.0" not in text, path
        assert install_snippet in text, path


def test_public_docs_use_executable_asr_api_url_setting_name():
    for path in [ROOT / "README.md", ROOT / "README.en.md", ROOT / "docs" / "deployment.md", ROOT / "docs" / "deployment.en.md"]:
        text = _read(path)
        assert "<ASR_API_URL_SETTING>" not in text, path
        assert "CHATVOICE_ASR_API_URL" in text, path
        assert "the ASR API URL setting" not in text, path


def test_public_docs_state_summary_configuration_boundary():
    expected_fragments = [
        "summary",
        "server-side",
        "model",
    ]
    for path in [ROOT / "README.md", ROOT / "README.en.md", ROOT / "docs" / "deployment.md", ROOT / "docs" / "deployment.en.md"]:
        text = _read(path).lower()
        for fragment in expected_fragments:
            assert fragment in text, path


def test_public_docs_explain_runtime_layout_data_schema_and_concurrency_todo():
    required = [
        "site-packages",
        "~/.chatarch/chatvoice",
        "CHATVOICE_HOME",
        "CHATARCH_HOME",
        "meetings.sqlite3",
        "accounts",
        "api_tokens",
        "meeting_records",
        "conversation_records",
        "temp/asr",
        "model-cache",
        "Postgres/MySQL",
    ]
    for path in [ROOT / "README.md", ROOT / "README.en.md", ROOT / "docs" / "deployment.md", ROOT / "docs" / "deployment.en.md"]:
        text = _read(path)
        for fragment in required:
            assert fragment in text, (path, fragment)
