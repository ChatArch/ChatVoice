import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _client_with_temp_db(monkeypatch, tmp_path):
    from chatvoice.web import legacy_app

    monkeypatch.setattr(legacy_app, "MEETING_DB_PATH", tmp_path / "meetings.sqlite3")
    return TestClient(legacy_app.app), legacy_app


def _login_user(client, legacy_app, account="alice@example.invalid", password="correct-horse"):
    legacy_app.provision_managed_account(account, password, "Alice")
    response = client.post("/api/auth/login", json={"account": account, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def _sample_meeting_payload():
    return {
        "title": "项目周会",
        "created_at": "2026-08-18T10:00:00+00:00",
        "updated_at": "2026-08-18T10:02:00+00:00",
        "duration_seconds": 120,
        "transcript_segments": [
            {"speaker": "说话人 1", "time": "00:01", "text": "我们确认 ChatVoice 0.1 的 token 数据接口。"},
            {"speaker": "说话人 2", "time": "00:30", "text": "后续自动化可以拉取摘要和转写。"},
        ],
        "summary_title": "ChatVoice 0.1 数据接口",
        "summary_content": "确认新增 API Token，并支持外部拉取转写与摘要。",
        "summary_customized": True,
        "summary_chat_messages": [{"role": "user", "text": "请整理后续动作"}, {"role": "assistant", "text": "已整理。"}],
    }


def _sample_conversation_payload():
    return {
        "title": "实时对话",
        "model": "qwen-audio-3.0-realtime-plus",
        "voice": "Cherry",
        "created_at": "2026-08-18T10:03:00+00:00",
        "updated_at": "2026-08-18T10:04:00+00:00",
        "messages": [
            {"role": "user", "text": "今天同步 ChatVoice 0.1。"},
            {"role": "assistant", "text": "我会记录 token 和数据读取。"},
        ],
    }


def _create_token(client, csrf, scopes=None, *, expires_days=30):
    payload = {"name": "automation", "expires_days": expires_days}
    if scopes is not None:
        payload["scopes"] = scopes
    response = client.post("/api/tokens", headers={"X-CSRF-Token": csrf}, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_authenticated_user_can_create_list_and_revoke_api_tokens(monkeypatch, tmp_path):
    client, legacy_app = _client_with_temp_db(monkeypatch, tmp_path)
    csrf = _login_user(client, legacy_app)

    created = client.post(
        "/api/tokens",
        headers={"X-CSRF-Token": csrf},
        json={"name": "automation", "expires_days": 30, "scopes": ["read:meetings", "read:conversations"]},
    )

    assert created.status_code == 200, created.text
    created_payload = created.json()
    assert created_payload["token"].startswith("cv_")
    assert created_payload["token"][3:11] == created_payload["token_info"]["prefix"]
    assert created_payload["token_info"]["name"] == "automation"
    assert created_payload["token_info"]["revoked_at"] is None

    token = created_payload["token"]
    listed = client.get("/api/tokens")
    assert listed.status_code == 200, listed.text
    listed_payload = listed.json()
    assert listed_payload["tokens"][0]["id"] == created_payload["token_info"]["id"]
    assert token not in json.dumps(listed_payload, ensure_ascii=False)

    revoked = client.delete(f"/api/tokens/{created_payload['token_info']['id']}", headers={"X-CSRF-Token": csrf})
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked"] is True

    listed_after = client.get("/api/tokens")
    assert listed_after.status_code == 200, listed_after.text
    assert listed_after.json()["tokens"][0]["revoked_at"]


def test_api_token_creation_rejects_empty_or_unsupported_scopes(monkeypatch, tmp_path):
    client, legacy_app = _client_with_temp_db(monkeypatch, tmp_path)
    csrf = _login_user(client, legacy_app)

    empty = client.post("/api/tokens", headers={"X-CSRF-Token": csrf}, json={"name": "empty", "scopes": []})
    assert empty.status_code == 400, empty.text
    assert "at least one" in empty.text

    unsupported = client.post(
        "/api/tokens",
        headers={"X-CSRF-Token": csrf},
        json={"name": "bad", "scopes": ["read:meetings", "write:meetings"]},
    )
    assert unsupported.status_code == 400, unsupported.text
    assert "unsupported token scope" in unsupported.text

    listed = client.get("/api/tokens")
    assert listed.status_code == 200, listed.text
    assert listed.json()["tokens"] == []


def test_token_create_and_revoke_require_csrf(monkeypatch, tmp_path):
    client, legacy_app = _client_with_temp_db(monkeypatch, tmp_path)
    csrf = _login_user(client, legacy_app)

    no_csrf_create = client.post("/api/tokens", json={"name": "missing-csrf"})
    assert no_csrf_create.status_code == 403

    created = _create_token(client, csrf)
    no_csrf_revoke = client.delete(f"/api/tokens/{created['token_info']['id']}")
    assert no_csrf_revoke.status_code == 403


def test_single_scope_token_only_authorizes_matching_data(monkeypatch, tmp_path):
    client, legacy_app = _client_with_temp_db(monkeypatch, tmp_path)
    csrf = _login_user(client, legacy_app)
    meeting_token = _create_token(client, csrf, ["read:meetings"])["token"]
    conversation_token = _create_token(client, csrf, ["read:conversations"])["token"]

    assert client.put("/api/meetings/meeting_20260818", headers={"X-CSRF-Token": csrf}, json=_sample_meeting_payload()).status_code == 200
    assert client.put("/api/conversations/conversation_20260818", headers={"X-CSRF-Token": csrf}, json=_sample_conversation_payload()).status_code == 200

    meeting_list = client.get("/api/data/meetings", headers={"Authorization": f"Bearer {meeting_token}"})
    assert meeting_list.status_code == 200, meeting_list.text
    assert "transcript_segments" not in meeting_list.json()["meetings"][0]
    assert "summary_content" not in meeting_list.json()["meetings"][0]

    meeting_detail = client.get("/api/data/meetings/meeting_20260818", headers={"Authorization": f"Bearer {meeting_token}"})
    assert meeting_detail.status_code == 200, meeting_detail.text
    assert meeting_detail.json()["transcript_segments"][1]["text"] == "后续自动化可以拉取摘要和转写。"
    assert meeting_detail.json()["summary_content"].startswith("确认新增 API Token")

    blocked_conversations = client.get("/api/data/conversations", headers={"Authorization": f"Bearer {meeting_token}"})
    assert blocked_conversations.status_code == 403

    conversation_list = client.get("/api/data/conversations", headers={"Authorization": f"Bearer {conversation_token}"})
    assert conversation_list.status_code == 200, conversation_list.text
    assert "messages" not in conversation_list.json()["conversations"][0]

    conversation_detail = client.get("/api/data/conversations/conversation_20260818", headers={"Authorization": f"Bearer {conversation_token}"})
    assert conversation_detail.status_code == 200, conversation_detail.text
    assert conversation_detail.json()["messages"][1]["text"] == "我会记录 token 和数据读取。"

    blocked_meetings = client.get("/api/data/meetings", headers={"Authorization": f"Bearer {conversation_token}"})
    assert blocked_meetings.status_code == 403


def test_expired_token_is_rejected(monkeypatch, tmp_path):
    client, legacy_app = _client_with_temp_db(monkeypatch, tmp_path)
    issued_at = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(legacy_app, "_utc_now", lambda: issued_at)
    csrf = _login_user(client, legacy_app)
    token = _create_token(client, csrf, ["read:meetings"], expires_days=1)["token"]

    monkeypatch.setattr(legacy_app, "_utc_now", lambda: issued_at + timedelta(days=2))
    rejected = client.get("/api/data/meetings", headers={"Authorization": f"Bearer {token}"})
    assert rejected.status_code == 401
    assert "expired" in rejected.text


def test_bearer_token_can_read_meeting_text_and_summary(monkeypatch, tmp_path):
    client, legacy_app = _client_with_temp_db(monkeypatch, tmp_path)
    csrf = _login_user(client, legacy_app)
    token_payload = client.post(
        "/api/tokens",
        headers={"X-CSRF-Token": csrf},
        json={"name": "downstream"},
    ).json()
    token = token_payload["token"]

    saved = client.put(
        "/api/meetings/meeting_20260818",
        headers={"X-CSRF-Token": csrf},
        json=_sample_meeting_payload(),
    )
    assert saved.status_code == 200, saved.text

    unauthorized = client.get("/api/data/meetings")
    assert unauthorized.status_code == 401

    listed = client.get("/api/data/meetings", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200, listed.text
    meeting = listed.json()["meetings"][0]
    assert meeting["id"] == "meeting_20260818"
    assert meeting["title"] == "项目周会"
    assert "summary_content" not in meeting
    assert "transcript_segments" not in meeting

    single = client.get("/api/data/meetings/meeting_20260818", headers={"Authorization": f"Bearer {token}"})
    assert single.status_code == 200, single.text
    assert single.json()["title"] == "项目周会"
    assert single.json()["summary_title"] == "ChatVoice 0.1 数据接口"
    assert single.json()["summary_content"].startswith("确认新增 API Token")
    assert single.json()["transcript_segments"][1]["text"] == "后续自动化可以拉取摘要和转写。"

    revoked = client.delete(f"/api/tokens/{token_payload['token_info']['id']}", headers={"X-CSRF-Token": csrf})
    assert revoked.status_code == 200, revoked.text
    rejected = client.get("/api/data/meetings", headers={"Authorization": f"Bearer {token}"})
    assert rejected.status_code == 401
