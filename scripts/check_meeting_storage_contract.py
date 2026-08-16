#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import main  # noqa: E402


checks: dict[str, bool] = {}

with tempfile.TemporaryDirectory() as directory:
    main.MEETING_DB_PATH = Path(directory) / "meetings.sqlite3"
    anonymous = TestClient(main.app)
    checks["anonymous_server_records_are_blocked"] = anonymous.get("/api/meetings").status_code == 401

    client = TestClient(main.app)
    register = client.post("/api/auth/register", json={"account": "contract@example.com", "password": "correct-horse-123"})
    register_payload = register.json()
    csrf_token = register_payload.get("csrf_token", "")
    checks["account_can_register"] = register.status_code == 200 and bool(csrf_token) and "meeting_session" in client.cookies
    checks["password_is_not_returned"] = "password" not in json.dumps(register_payload).lower()

    session = client.get("/api/auth/session")
    checks["cookie_session_is_restored"] = session.status_code == 200 and session.json().get("authenticated") is True

    meeting_id = "meeting_contract_1234"
    record = {
        "title": "合同测试会议",
        "created_at": "2026-08-17T05:00:00+08:00",
        "updated_at": "2026-08-17T05:01:00+08:00",
        "duration_seconds": 61,
        "transcript_segments": [{"speaker": "说话人 1", "time": "00:03", "text": "这是服务端账号记录。"}],
        "summary_title": "合同测试摘要",
        "summary_content": "摘要内容。",
    }
    no_csrf = client.put(f"/api/meetings/{meeting_id}", json=record)
    checks["writes_require_csrf"] = no_csrf.status_code == 403

    saved = client.put(f"/api/meetings/{meeting_id}", json=record, headers={"X-CSRF-Token": csrf_token})
    listed = client.get("/api/meetings")
    loaded = client.get(f"/api/meetings/{meeting_id}")
    checks["logged_in_record_roundtrip"] = (
        saved.status_code == 200
        and listed.status_code == 200
        and len(listed.json().get("meetings", [])) == 1
        and loaded.json().get("summary_content") == "摘要内容。"
    )

    other = TestClient(main.app)
    other_register = other.post("/api/auth/register", json={"account": "other@example.com", "password": "correct-horse-456"})
    checks["accounts_are_isolated"] = other_register.status_code == 200 and other.get("/api/meetings").json().get("meetings") == []

    deleted = client.delete(f"/api/meetings/{meeting_id}", headers={"X-CSRF-Token": csrf_token})
    checks["record_can_be_deleted"] = deleted.status_code == 200 and client.get("/api/meetings").json().get("meetings") == []

    logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})
    checks["logout_invalidates_session"] = logout.status_code == 200 and client.get("/api/meetings").status_code == 401

checks["ok"] = all(checks.values())
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if checks["ok"] else 1)
