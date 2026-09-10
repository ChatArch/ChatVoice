"""Offline compatibility tests: old host rows, real published ChatLogin core."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
from importlib.resources import files
import sqlite3

import chatlogin
from fastapi.testclient import TestClient
import pytest

PASSWORD = "synthetic-test-password"
NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
OLD_TOKEN = "synthetic-legacy-session-token"
OLD_CSRF = "c" * 32
SCHEMA = """
CREATE TABLE accounts (id TEXT PRIMARY KEY, account TEXT NOT NULL UNIQUE,
 display_name TEXT NOT NULL, password_salt BLOB NOT NULL,
 password_hash BLOB NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE auth_sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
 csrf_token TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 FOREIGN KEY (user_id) REFERENCES accounts(id) ON DELETE CASCADE);
"""


@pytest.fixture
def host(monkeypatch, tmp_path):
    from chatvoice.web import legacy_app as app
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        for name in ("alice", "bob"):
            salt = name.encode().ljust(16, b"x")
            digest = hashlib.pbkdf2_hmac("sha256", PASSWORD.encode(), salt, 310000)
            db.execute("INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?)",
                       ("usr_" + name, name + "@example.invalid", name.title(), salt, digest, NOW.isoformat()))
        db.execute("INSERT INTO auth_sessions VALUES (?, ?, ?, ?, ?)",
                   (hashlib.sha256(OLD_TOKEN.encode()).hexdigest(), "usr_alice", OLD_CSRF,
                    NOW.isoformat(), (NOW + timedelta(days=30)).isoformat()))
    monkeypatch.setattr(app, "MEETING_DB_PATH", path)
    monkeypatch.setattr(app, "_utc_now", lambda: NOW)
    return app, TestClient(app.app)


def login(client, name="alice"):
    response = client.post("/api/auth/login", json={"account": " " + name.upper() + "@EXAMPLE.INVALID ", "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_host_uses_chatlogin_adapter():
    assert importlib.util.find_spec("chatvoice.web.auth_adapter") is not None, "missing real ChatLogin bridge"


def test_real_core_handles_login_resolve_csrf_revoke(host, monkeypatch):
    app, client = host
    import chatvoice.web.auth_adapter as adapter
    calls = []
    def spy(obj, name):
        original = getattr(obj, name)
        def wrapped(*args, **kwargs):
            calls.append(name)
            return original(*args, **kwargs)
        monkeypatch.setattr(obj, name, wrapped)
    for name in ("issue", "resolve", "revoke"):
        spy(chatlogin.SessionManager, name)
    spy(chatlogin.CallbackBackend, "authenticate")
    spy(adapter, "verify_pbkdf2")
    spy(adapter, "require_csrf")
    csrf = login(client)
    token = client.cookies.get("meeting_session")
    payload = client.get("/api/auth/session").json()
    assert payload["user"] == {"id": "usr_alice", "account": "alice@example.invalid", "display_name": "Alice"}
    assert payload["csrf_token"] == csrf
    with closing(app._meeting_db()) as db:
        row = db.execute("SELECT * FROM auth_sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        assert row["user_id"] == "usr_alice"
        assert datetime.fromisoformat(row["expires_at"]) == NOW + timedelta(days=30)
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).json() == {"authenticated": False}
    client.cookies.set("meeting_session", token)
    assert client.get("/api/auth/session").json() == {"authenticated": False}
    assert {"authenticate", "verify_pbkdf2", "issue", "resolve", "require_csrf", "revoke"} <= set(calls)


def test_legacy_session_and_live_account_join(host, monkeypatch):
    app, client = host
    client.cookies.set("meeting_session", OLD_TOKEN)
    assert client.get("/api/auth/session").json()["csrf_token"] == OLD_CSRF
    with closing(app._meeting_db()) as db:
        db.execute("UPDATE accounts SET display_name = 'Updated' WHERE id = 'usr_alice'")
        db.commit()
    assert client.get("/api/auth/session").json()["user"]["display_name"] == "Updated"
    monkeypatch.setattr(app, "_utc_now", lambda: NOW + timedelta(days=30))
    assert client.get("/api/auth/session").json() == {"authenticated": False}
    with closing(app._meeting_db()) as db:
        assert db.execute("SELECT count(*) FROM auth_sessions").fetchone()[0] == 0


def test_missing_and_bad_password_fail_without_identity(host, monkeypatch):
    _, client = host
    import chatvoice.web.auth_adapter as adapter
    original = adapter.verify_pbkdf2
    checked = []
    def verify(*args, **kwargs):
        checked.append(kwargs["iterations"])
        return original(*args, **kwargs)
    monkeypatch.setattr(adapter, "verify_pbkdf2", verify)
    for account in ("alice@example.invalid", "missing@example.invalid"):
        response = client.post("/api/auth/login", json={"account": account, "password": "wrong-password", "user_id": "usr_alice", "role": "admin"})
        assert response.status_code == 401
        assert "set-cookie" not in response.headers
    assert checked == [310000, 310000]
    assert client.post("/api/auth/register", json={}).status_code == 403


def test_path_monkeypatch_follows_existing_adapter(host, monkeypatch, tmp_path):
    app, client = host
    login(client)
    monkeypatch.setattr(app, "MEETING_DB_PATH", tmp_path / "other.sqlite3")
    assert client.get("/api/auth/session").json() == {"authenticated": False}
    assert client.post("/api/auth/login", json={"account": "alice@example.invalid", "password": PASSWORD}).status_code == 401


def test_schema_and_auth_dialog_bytes_unchanged(host):
    app, client = host
    with closing(app._meeting_db()) as db:
        before = db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        hashes = db.execute("SELECT password_salt, password_hash FROM accounts ORDER BY id").fetchall()
    login(client)
    with closing(app._meeting_db()) as db:
        assert db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall() == before
        assert db.execute("SELECT password_salt, password_hash FROM accounts ORDER BY id").fetchall() == hashes
    # Preserve the released login/guest UI, not unrelated product features.
    # This golden fragment also works without Git history in installed wheels.
    html = (files("chatvoice.web") / "static" / "index.html").read_text(encoding="utf-8")
    start = html.index('<dialog id="entry-dialog"')
    dialog = html[start:html.index('</dialog>', start) + len('</dialog>')]
    assert hashlib.sha256(dialog.encode()).hexdigest() == "fbc54c0acb7fa6a9d0ccacc9cc7dd6910e372b2dfc66838ddcacaa665a3e779c"


def test_owner_isolation_same_id_and_guest_cloud_denial(host):
    app, alice = host
    bob, guest = TestClient(app.app), TestClient(app.app)
    for client, name in ((alice, "alice"), (bob, "bob")):
        csrf = login(client, name)
        for kind, extra in (("meetings", {}), ("conversations", {"model": "synthetic", "voice": "test", "messages": []})):
            data = {"title": name, "created_at": NOW.isoformat(), "updated_at": NOW.isoformat(), **extra}
            assert client.put(f"/api/{kind}/same-record-id", headers={"X-CSRF-Token": csrf}, json=data).status_code == 200
            assert client.get(f"/api/{kind}/same-record-id").json()["title"] == name
    for kind in ("meetings", "conversations"):
        assert alice.get(f"/api/{kind}/same-record-id").json()["title"] == "alice"
        assert bob.get(f"/api/{kind}/same-record-id").json()["title"] == "bob"
        assert guest.get(f"/api/{kind}/same-record-id").status_code == 401
        assert guest.get(f"/api/{kind}").status_code == 401
    assert guest.get("/api/auth/session").json() == {"authenticated": False}


def test_store_namespace_capacity_atomic_replace_and_role(host):
    app, _ = host
    from chatvoice.web.auth_adapter import HostSessionStore
    store = HostSessionStore(lambda: app._meeting_db(), lambda: app._MEETING_DB_LOCK,
                             lambda: app._utc_now().timestamp(), max_sessions=1)
    session = store.get("chatvoice", hashlib.sha256(OLD_TOKEN.encode()).hexdigest())
    assert session.principal.role is chatlogin.Role.USER
    old_digest = hashlib.sha256(OLD_TOKEN.encode()).hexdigest()
    new_digest = "a" * 64
    with pytest.raises(chatlogin.StoreFull):
        store.put("chatvoice", new_digest, session)
    store.put("chatvoice", new_digest, session, previous_digest=old_digest)
    assert store.get("chatvoice", old_digest) is None
    assert store.get("chatvoice", new_digest) == session
    with pytest.raises(ValueError):
        store.put("chatvoice", new_digest, session, previous_digest=new_digest)
    assert store.get("chatvoice", new_digest) == session
    for operation in (
        lambda: store.get("other", new_digest), lambda: store.delete("other", new_digest),
        lambda: store.put("other", old_digest, session), lambda: store.purge_expired("other", NOW.timestamp()),
    ):
        with pytest.raises(ValueError):
            operation()
    store.purge_expired("chatvoice", session.expires_at)
    assert store.get("chatvoice", new_digest) is None
