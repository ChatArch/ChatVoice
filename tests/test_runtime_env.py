import importlib
import sys


def test_legacy_web_runtime_root_respects_chatarch_home(monkeypatch, tmp_path):
    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.delenv("CHATVOICE_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("CHATVOICE_HOME", raising=False)
    monkeypatch.delenv("MEETING_DB_PATH", raising=False)
    monkeypatch.delenv("CHATVOICE_SQLITE_PATH", raising=False)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))

    legacy_app = importlib.import_module(module_name)
    try:
        assert legacy_app.RUNTIME_ROOT == tmp_path / "chatarch-home" / "chatvoice"
        assert legacy_app.MEETING_DB_PATH == legacy_app.RUNTIME_ROOT / "data" / "meetings.sqlite3"
    finally:
        sys.modules.pop(module_name, None)
        importlib.import_module(module_name)
