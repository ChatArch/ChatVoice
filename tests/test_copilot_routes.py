"""Authenticated Copilot API routes: ownership, upload validation and SSE."""

import asyncio
from contextlib import closing
import importlib
import io
import json
import socket
import sys

import fastapi.routing
import httpx
import pytest
import starlette.responses


@pytest.fixture
def copilot_app(monkeypatch, tmp_path):
    monkeypatch.setattr(socket.socket, "connect", lambda *args, **kwargs: pytest.fail("Real network forbidden"))

    async def deterministic_executor(function, *args, **kwargs):
        return function(*args, **kwargs)

    async def deterministic_iterator(iterator):
        for item in iterator:
            yield item

    monkeypatch.setattr(fastapi.routing, "run_in_threadpool", deterministic_executor)
    monkeypatch.setattr(asyncio, "to_thread", deterministic_executor)
    monkeypatch.setattr(starlette.responses, "iterate_in_threadpool", deterministic_iterator)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch"))
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "voice"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")
    monkeypatch.setenv("CHATVOICE_ASR_PREWARM", "0")
    monkeypatch.setenv("CHATVOICE_COPILOT_ENABLED", "1")
    monkeypatch.setenv("CHATVOICE_MEETING_NOTES_API_BASE", "https://notes.example.test/v1")
    monkeypatch.setenv("CHATVOICE_MEETING_NOTES_API_KEY", "offline-secret")
    monkeypatch.setenv("CHATVOICE_MEETING_NOTES_MODEL", "offline-model")
    name = "chatvoice.web.legacy_app"
    sys.modules.pop(name, None)
    module = importlib.import_module(name)
    monkeypatch.setattr(module, "MEETING_DB_PATH", tmp_path / "copilot.sqlite3")
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("legacy network path used"))
    yield module
    sys.modules.pop(name, None)


async def _login(client, module, account):
    module.provision_managed_account(account, "offline-password", account)
    result = await client.post("/api/auth/login", json={"account": account, "password": "offline-password"})
    assert result.status_code == 200, result.text
    return {"X-CSRF-Token": result.json()["csrf_token"]}


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, timeout=12))


def test_copilot_page_and_status_follow_feature_flag(copilot_app, monkeypatch):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=copilot_app.app), base_url="https://app.example.test") as client:
            page = await client.get("/copilot")
            assert page.status_code == 200
            assert "会中助手" in page.text
            status = (await client.get("/api/copilot/status")).json()
            assert status["enabled"] is True
            monkeypatch.setattr(copilot_app, "COPILOT_ENABLED", False)
            assert (await client.get("/copilot")).status_code == 404
            assert (await client.get("/api/copilot/status")).json()["enabled"] is False
    run(scenario())


def test_material_upload_is_authenticated_csrf_owned_and_validated(copilot_app):
    async def scenario():
        transport = httpx.ASGITransport(app=copilot_app.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://app.example.test") as owner, httpx.AsyncClient(transport=transport, base_url="https://app.example.test") as other:
            assert (await owner.post("/api/copilot/materials", files={"file": ("a.txt", b"secret", "text/plain")})).status_code == 401
            csrf = await _login(owner, copilot_app, "owner@example.test")
            other_csrf = await _login(other, copilot_app, "other@example.test")
            assert (await owner.post("/api/copilot/materials", files={"file": ("a.txt", b"secret", "text/plain")})).status_code == 403
            uploaded = await owner.post("/api/copilot/materials", headers=csrf, files={"file": ("方案.md", "# 标题\n\n企业版支持 SSO。", "text/markdown")})
            assert uploaded.status_code == 200, uploaded.text
            material = uploaded.json()["material"]
            assert material["filename"] == "方案.md"
            assert "企业版支持 SSO" in material["preview"]
            assert (await other.get("/api/copilot/materials")).json()["materials"] == []
            assert (await other.delete(f"/api/copilot/materials/{material['id']}", headers=other_csrf)).status_code == 404
            assert len((await owner.get("/api/copilot/materials")).json()["materials"]) == 1
            scan = await owner.post("/api/copilot/materials", headers=csrf, files={"file": ("scan.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")})
            assert scan.status_code == 422
            assert "OCR" in scan.text
            copilot_app.MAX_COPILOT_MATERIAL_BYTES = 32
            huge = await owner.post("/api/copilot/materials", headers=csrf, files={"file": ("huge.txt", b"x" * 33, "text/plain")})
            assert huge.status_code == 413
            assert (await owner.delete(f"/api/copilot/materials/{material['id']}", headers=csrf)).status_code == 200
            assert (await owner.get("/api/copilot/materials")).json()["materials"] == []
    run(scenario())


def test_answer_stream_uses_notes_settings_and_reports_empty_error(copilot_app, monkeypatch):
    from chatvoice import text_api

    calls = []

    def fake_open(request, timeout):
        payload = json.loads(request.data)
        calls.append(payload)
        assert request.full_url == "https://notes.example.test/v1/chat/completions"
        assert request.get_header("Authorization") == "Bearer offline-secret"
        assert payload["model"] == "offline-model"
        assert set(payload) <= {"model", "messages", "stream", "max_tokens"}
        body = 'data: ' + json.dumps({"choices": [{"delta": {"content": "可以这样回答。"}}]}) + "\n\ndata: [DONE]\n\n"
        return io.BytesIO(body.encode())

    monkeypatch.setattr(text_api, "_open_request", fake_open)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=copilot_app.app), base_url="https://app.example.test") as client:
            csrf = await _login(client, copilot_app, "asker@example.test")
            await client.post("/api/copilot/materials", headers=csrf, files={"file": ("方案.txt", "企业版支持 SSO。".encode(), "text/plain")})
            response = await client.post("/api/copilot/answer/stream", headers=csrf, json={
                "question": "SSO 怎么回答？",
                "transcript": "客户问企业版是否支持 SSO。",
                "instructions": "简短中文",
                "request_id": "manual-1",
                "transcript_revision": 7,
                "material_revision": 1,
            })
            assert response.status_code == 200
            assert "event: delta" in response.text
            assert "event: done" in response.text
            assert "可以这样回答" in response.text
            assert len(calls) == 1
            monkeypatch.setattr(text_api, "_open_request", lambda *_a, **_k: io.BytesIO(b"data: [DONE]\n\n"))
            failed = await client.post("/api/copilot/answer/stream", headers=csrf, json={
                "question": "空答复？", "transcript": "内容", "request_id": "manual-2"
            })
            assert "event: error" in failed.text and "event: done" not in failed.text
    run(scenario())


def test_copilot_tables_live_in_host_sqlite(copilot_app):
    with closing(copilot_app._meeting_db()) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "copilot_materials" in tables
