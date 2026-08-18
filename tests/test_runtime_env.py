import importlib
import sys

from fastapi.testclient import TestClient


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


def test_runtime_path_resolver_matches_web_app_overrides(monkeypatch, tmp_path):
    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "ignored-chatarch-home"))
    monkeypatch.setenv("CHATVOICE_RUNTIME_ROOT", str(tmp_path / "runtime-root"))
    monkeypatch.delenv("CHATVOICE_HOME", raising=False)
    monkeypatch.delenv("MEETING_DB_PATH", raising=False)
    monkeypatch.delenv("CHATVOICE_SQLITE_PATH", raising=False)

    from chatvoice.paths import state_paths

    legacy_app = importlib.import_module(module_name)
    try:
        paths = state_paths()
        assert paths.root == tmp_path / "runtime-root"
        assert paths.database_path == tmp_path / "runtime-root" / "data" / "meetings.sqlite3"
        assert legacy_app.RUNTIME_ROOT == paths.root
        assert legacy_app.MEETING_DB_PATH == paths.database_path
    finally:
        sys.modules.pop(module_name, None)
        importlib.import_module(module_name)


def test_runtime_path_resolver_matches_web_app_sqlite_path_alias(monkeypatch, tmp_path):
    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    sqlite_path = tmp_path / "explicit" / "service.sqlite3"
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.setenv("CHATVOICE_SQLITE_PATH", str(sqlite_path))
    monkeypatch.delenv("CHATVOICE_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("CHATVOICE_HOME", raising=False)
    monkeypatch.delenv("MEETING_DB_PATH", raising=False)

    from chatvoice.paths import state_paths

    legacy_app = importlib.import_module(module_name)
    try:
        paths = state_paths()
        assert paths.database_path == sqlite_path
        assert legacy_app.MEETING_DB_PATH == sqlite_path
    finally:
        sys.modules.pop(module_name, None)
        importlib.import_module(module_name)


def test_accounts_cli_and_web_app_share_chatarch_home_database(monkeypatch, tmp_path):
    module_name = "chatvoice.web.legacy_app"
    sys.modules.pop(module_name, None)
    monkeypatch.delenv("CHATVOICE_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("CHATVOICE_HOME", raising=False)
    monkeypatch.delenv("MEETING_DB_PATH", raising=False)
    monkeypatch.delenv("CHATVOICE_SQLITE_PATH", raising=False)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))

    from chatvoice.accounts import create_account, list_accounts
    legacy_app = importlib.import_module(module_name)

    try:
        created = create_account("person@example.com", "correct horse battery", "Person")
        assert created["account"] == "person@example.com"
        assert legacy_app.MEETING_DB_PATH == tmp_path / "chatarch-home" / "chatvoice" / "data" / "meetings.sqlite3"
        assert legacy_app.MEETING_DB_PATH.exists()
        assert [account["account"] for account in list_accounts()] == ["person@example.com"]

        client = TestClient(legacy_app.app)
        response = client.post("/api/auth/login", json={"account": "person@example.com", "password": "correct horse battery"})
        assert response.status_code == 200, response.text
    finally:
        sys.modules.pop(module_name, None)
        importlib.import_module(module_name)
