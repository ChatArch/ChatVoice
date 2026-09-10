"""Reader-facing ChatArch documentation contracts."""
from pathlib import Path
import re

from chatvoice.config import ChatVoiceConfig

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_bilingual_pages_are_complete():
    missing = [p.name for p in DOCS.glob("*.md") if not p.name.endswith(".en.md") and not p.with_name(p.stem + ".en.md").exists()]
    assert missing == []


def test_scenario_hubs_and_grouped_navigation():
    for name in ("index.md", "index.en.md", "quickstart.md", "quickstart.en.md"):
        text = (DOCS / name).read_text()
        assert 'class="grid cards"' in text
    config = (ROOT / "mkdocs.yml").read_text()
    for entry in ("开始使用:", "功能指南:", "配置与运维:", "接口参考:", "开发验证:", "pymdownx.emoji", "material.extensions.emoji.twemoji", "material.extensions.emoji.to_svg"):
        assert entry in config


def test_configuration_reference_covers_the_real_schema():
    for name in ("configuration.md", "configuration.en.md"):
        text = (DOCS / name).read_text()
        assert all(key in text for key in ChatVoiceConfig.get_fields())
        assert "chatenv paste --stdin" in text
        assert "chatenv use speakr -t chatvoice -I" in text


def test_cli_reference_is_segmented_not_a_single_dump():
    for name in ("cli-tree.md", "cli-tree.en.md"):
        text = (DOCS / name).read_text()
        assert text.count("```text") >= 5
        for command in ("serve", "accounts", "tokens", "data", "service", "health"):
            assert command in text


def test_formal_docs_do_not_contain_run_logs_or_private_home_paths():
    for path in list(DOCS.glob("*.md")) + [ROOT / "README.md", ROOT / "README.en.md"]:
        text = path.read_text()
        assert not re.search(r"/home/(?!<)|/Users/(?!<)|本次验收|已完成.*公网验收|本 PR|本轮|Phase [0-9]", text), path.name


def test_todo_and_runtime_interfaces_are_documented():
    for name in ("interface-tree.md", "interface-tree.en.md"):
        text = (DOCS / name).read_text()
        for api in ("dump_database", "import_database", "generate_todo", "revise_todo", "create_app"):
            assert api in text
    for name in ("api-access.md", "api-access.en.md"):
        text = (DOCS / name).read_text()
        for route in ("/api/meeting-notes/todo", "/api/meeting-notes/todo/revise", "todo_markdown", "todo_chat_messages"):
            assert route in text
