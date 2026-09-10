"""Markdown Todo persistence uses the real meeting/auth/CSRF routes."""
import asyncio
from contextlib import closing
import importlib
import sqlite3
import sys

import fastapi.routing
import httpx
import pytest

@pytest.fixture
def todo_app(monkeypatch, tmp_path):
    async def in_thread(function, *args, **kwargs):
        return function(*args, **kwargs)
    monkeypatch.setattr(fastapi.routing, "run_in_threadpool", in_thread)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch"))
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "voice"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")
    monkeypatch.setenv("CHATVOICE_ASR_PREWARM", "0")
    sys.modules.pop("chatvoice.web.legacy_app", None)
    app = importlib.import_module("chatvoice.web.legacy_app")
    monkeypatch.setattr(app, "MEETING_DB_PATH", tmp_path / "meetings.sqlite3")
    yield app
    sys.modules.pop("chatvoice.web.legacy_app", None)

PAYLOAD = {"title": "Todo record", "created_at": "2026-09-11T00:00:00Z", "updated_at": "2026-09-11T00:00:00Z", "summary_content": "整理报告"}
MARKDOWN = "# 行动计划\n- [x] 核对范围\n- [ ] 整理报告"
CHAT = [{"role": "user", "text": "保留已完成项"}, {"role": "assistant", "text": "已保留。"}]

async def login(client, module, account):
    module.provision_managed_account(account, "test-only-password", account)
    result = await client.post("/api/auth/login", json={"account": account, "password": "test-only-password"})
    assert result.status_code == 200
    return {"X-CSRF-Token": result.json()["csrf_token"]}


def test_todo_persist_omission_clear_and_owner_boundary(todo_app):
    async def flow():
        transport = httpx.ASGITransport(app=todo_app.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://app.example.test") as owner, httpx.AsyncClient(transport=transport, base_url="https://app.example.test") as other:
            path = "/api/meetings/todo-sample"
            assert (await owner.get(path)).status_code == 401
            csrf = await login(owner, todo_app, "owner@example.test")
            await login(other, todo_app, "other@example.test")
            body = {**PAYLOAD, "todo_markdown": MARKDOWN, "todo_chat_messages": CHAT}
            assert (await owner.put(path, json=body)).status_code == 403
            result = await owner.put(path, json=body, headers=csrf)
            assert result.status_code == 200
            assert result.json().get("todo_markdown") == MARKDOWN
            assert (await owner.get(path)).json()["todo_chat_messages"] == CHAT
            assert (await other.get(path)).status_code == 404
            assert "todo_markdown" not in (await owner.get("/api/meetings")).json()["meetings"][0]
            # Existing clients may save other fields without knowing about Todo.
            assert (await owner.put(path, json=PAYLOAD, headers=csrf)).json()["todo_markdown"] == MARKDOWN
            assert (await owner.get(path)).json()["todo_chat_messages"] == CHAT
            cleared = await owner.put(path, json={**PAYLOAD,"todo_markdown":"","todo_chat_messages":[]}, headers=csrf)
            assert cleared.json()["todo_markdown"] == ""
            assert cleared.json()["todo_chat_messages"] == []
    asyncio.run(asyncio.wait_for(flow(), 15))


def test_todo_bearer_export(todo_app):
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=todo_app.app),base_url="https://app.example.test") as client:
            csrf=await login(client,todo_app,"owner@example.test")
            assert (await client.put("/api/meetings/export-todo",json={**PAYLOAD,"todo_markdown":MARKDOWN,"todo_chat_messages":CHAT},headers=csrf)).status_code==200
            created=await client.post("/api/tokens",json={"name":"test","scopes":["read:meetings"]},headers=csrf)
            auth={"Authorization":"Bearer "+created.json()["token"]}
            result=await client.get("/api/data/meetings/export-todo",headers=auth)
            assert result.status_code==200
            assert result.json().get("todo_markdown")==MARKDOWN
            assert result.json()["todo_chat_messages"]==CHAT
    asyncio.run(asyncio.wait_for(flow(),15))


@pytest.mark.parametrize("extra", [{"todo_markdown":"x"*20001},{"todo_chat_messages":[{"role":"system","text":"not allowed"}]},{"todo_chat_messages":[{"role":"user","text":"x"*4001}]}])
def test_todo_rejects_invalid_record_fields(todo_app,extra):
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=todo_app.app),base_url="https://app.example.test") as client:
            csrf=await login(client,todo_app,"owner@example.test")
            assert (await client.put("/api/meetings/invalid-todo",json={**PAYLOAD,**extra},headers=csrf)).status_code==422
    asyncio.run(asyncio.wait_for(flow(),15))


def test_todo_migrates_existing_meetings_as_empty(todo_app):
    with sqlite3.connect(todo_app.MEETING_DB_PATH) as db:
        db.execute("""CREATE TABLE meeting_records (
          owner_id TEXT NOT NULL, meeting_id TEXT NOT NULL, title TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          duration_seconds INTEGER NOT NULL DEFAULT 0, transcript_json TEXT NOT NULL DEFAULT '[]',
          summary_title TEXT NOT NULL DEFAULT '', summary_content TEXT NOT NULL DEFAULT '',
          preview TEXT NOT NULL DEFAULT '', PRIMARY KEY (owner_id, meeting_id))""")
        db.execute("INSERT INTO meeting_records(owner_id,meeting_id,title,created_at,updated_at,summary_content) VALUES('legacy-owner','legacy','旧会议','now','now','旧摘要')")
    with closing(todo_app._meeting_db()) as db:
        row=db.execute("SELECT * FROM meeting_records WHERE meeting_id='legacy'").fetchone()
        payload=todo_app._meeting_row_payload(row, True)
        assert payload.get("todo_markdown")==""
        assert payload["todo_chat_messages"]==[]
        assert payload["summary_content"]=="旧摘要"
