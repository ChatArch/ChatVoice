import json

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
    assert meeting["summary_title"] == "ChatVoice 0.1 数据接口"
    assert meeting["summary_content"].startswith("确认新增 API Token")
    assert meeting["transcript_segments"][1]["text"] == "后续自动化可以拉取摘要和转写。"

    single = client.get("/api/data/meetings/meeting_20260818", headers={"Authorization": f"Bearer {token}"})
    assert single.status_code == 200, single.text
    assert single.json()["title"] == "项目周会"

    revoked = client.delete(f"/api/tokens/{token_payload['token_info']['id']}", headers={"X-CSRF-Token": csrf})
    assert revoked.status_code == 200, revoked.text
    rejected = client.get("/api/data/meetings", headers={"Authorization": f"Bearer {token}"})
    assert rejected.status_code == 401
