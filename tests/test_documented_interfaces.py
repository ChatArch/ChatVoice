"""Documented routes must exist in the actual packaged application."""
from pathlib import Path
import re


def _route(path):
    return re.sub(r"\{[^}]+\}", "{}", path.split("?", 1)[0])


def test_documented_http_and_websocket_routes_exist():
    from chatvoice.web.legacy_app import app
    known = set()
    for route in app.routes:
        for method in getattr(route, "methods", None) or {"WS"}:
            known.add((method, _route(route.path)))
    docs = Path(__file__).resolve().parents[1] / "docs"
    for name in ("api-access.md", "api-access.en.md"):
        text = (docs / name).read_text()
        entries = re.findall(r"`(GET(?:/DELETE)?|POST|PUT|PATCH|DELETE|WS) (/[^`\s]+)`", text)
        assert entries
        for methods, path in entries:
            for method in methods.split("/"):
                assert (method, _route(path)) in known, (name, method, path)


def test_documented_python_examples_are_importable():
    from chatvoice import accounts, backup, client, paths, text_api, tts_api, todo_markdown
    from chatvoice.web import server
    for module, names in ((accounts, ("create_account", "list_accounts")), (backup, ("dump_database", "import_database")), (client, ("ChatVoiceClient", "list_remote_meetings", "get_remote_meeting")), (paths, ("state_paths",)), (text_api, ("resolve_text_settings", "complete_text", "stream_text")), (tts_api, ("resolve_tts_settings", "synthesize")), (todo_markdown, ("generate_todo", "revise_todo")), (server, ("create_app",))):
        for name in names:
            assert callable(getattr(module, name, None)), (module.__name__, name)
