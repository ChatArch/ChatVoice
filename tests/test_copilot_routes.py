"""Authenticated Copilot API routes: ownership, upload validation and SSE."""

import asyncio
from contextlib import closing
import importlib
import io
import json
import socket
import sys

import httpx
import pytest


@pytest.fixture
def copilot_app(monkeypatch, tmp_path):
    monkeypatch.setattr(socket.socket, "connect", lambda *args, **kwargs: pytest.fail("Real network forbidden"))
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
    return asyncio.run(coro)


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


def test_copilot_body_limit_runs_before_disabled_or_unauthenticated_handler(copilot_app, monkeypatch):
    monkeypatch.setattr(copilot_app, "MAX_COPILOT_MATERIAL_BYTES", 8)
    monkeypatch.setattr(copilot_app, "COPILOT_MATERIAL_ENVELOPE_BYTES", 8)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=copilot_app.app), base_url="https://app.example.test") as client:
            monkeypatch.setattr(copilot_app, "COPILOT_ENABLED", False)
            disabled = await client.post("/api/copilot/materials", files={"file": ("a.txt", b"small", "text/plain")})
            assert disabled.status_code == 413
            monkeypatch.setattr(copilot_app, "COPILOT_ENABLED", True)
            unauthenticated = await client.post("/api/copilot/materials", files={"file": ("a.txt", b"small", "text/plain")})
            assert unauthenticated.status_code == 413

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
        assert payload["max_tokens"] == copilot_app.COPILOT_MAX_TOKENS
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


def test_copilot_message_assembly_enforces_total_content_budget(copilot_app, monkeypatch):
    docs = [copilot_app.copilot_context.MaterialDocument(
        "m1", "pricing.txt", "客户可以选择 SSO 企业版方案。" * 30,
    )]
    monkeypatch.setattr(copilot_app, "_copilot_documents", lambda _owner: (docs, 3))
    request = copilot_app.CopilotAnswerRequest(
        question="客户现在需要怎样答复 SSO？" * 12,
        transcript="最近转写内容。" * 120,
        instructions="只根据上下文回答。" * 30,
        answer_style="简短中文。" * 20,
        request_id="bounded-message-test",
    )
    messages, _evidence, _revision = copilot_app._copilot_messages(
        request, "missing-owner", total_budget=3000,
    )
    assert request.question in messages[-1]["content"]
    assert "# Retrieved context from uploaded materials" in messages[-1]["content"]
    assert "# Evidence rendering note" not in messages[-1]["content"]
    assert sum(len(message["content"]) for message in messages) <= 3000


class _ControlledProvider:
    def __init__(self, values):
        self.values = iter(values)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.values)

    def close(self):
        self.closed = True


def test_copilot_asgi_disconnect_closes_provider_without_done(copilot_app, monkeypatch):
    from chatvoice import text_api

    provider = _ControlledProvider(["first", "second"])
    monkeypatch.setattr(text_api, "stream_text", lambda *_args, **_kwargs: provider)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=copilot_app.app), base_url="https://app.example.test") as client:
            csrf = await _login(client, copilot_app, "disconnect@example.test")
            body = json.dumps({"question": "现在怎么答？", "request_id": "disconnect-test"}).encode()
            cookie = client.cookies.get(copilot_app.AUTH_COOKIE_NAME)
            disconnect_ready = asyncio.Event()
            request_sent = False
            disconnect_delivered = False
            sent = []

            async def receive():
                nonlocal request_sent, disconnect_delivered
                if not request_sent:
                    request_sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                await disconnect_ready.wait()
                disconnect_delivered = True
                return {"type": "http.disconnect"}

            async def send(message):
                sent.append(message)
                if message["type"] == "http.response.body" and b"event: delta" in message.get("body", b""):
                    disconnect_ready.set()

            scope = {
                "type": "http", "asgi": {"version": "3.0", "spec_version": "2.0"}, "http_version": "1.1",
                "method": "POST", "scheme": "https", "path": "/api/copilot/answer/stream",
                "raw_path": b"/api/copilot/answer/stream", "query_string": b"",
                "headers": [
                    (b"host", b"app.example.test"), (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"cookie", f"{copilot_app.AUTH_COOKIE_NAME}={cookie}".encode()),
                    (b"x-csrf-token", csrf["X-CSRF-Token"].encode()),
                ],
                "client": ("127.0.0.1", 12345), "server": ("app.example.test", 443),
            }
            await copilot_app.app(scope, receive, send)
            response = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
            assert disconnect_delivered
            assert b"event: delta" in response
            assert b"event: done" not in response

    run(scenario())
    assert provider.closed


def test_copilot_asgi_logout_invalidates_stream_without_done(copilot_app, monkeypatch):
    from chatvoice import text_api

    provider = _ControlledProvider(["first", "second"])
    monkeypatch.setattr(text_api, "stream_text", lambda *_args, **_kwargs: provider)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=copilot_app.app), base_url="https://app.example.test") as client:
            csrf = await _login(client, copilot_app, "logout@example.test")
            body = json.dumps({"question": "现在怎么答？", "request_id": "logout-test"}).encode()
            cookie = client.cookies.get(copilot_app.AUTH_COOKIE_NAME)
            request_sent = False
            sent = []
            logged_out = []

            async def receive():
                nonlocal request_sent
                if not request_sent:
                    request_sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                await asyncio.Event().wait()

            async def send(message):
                sent.append(message)
                if message["type"] == "http.response.body" and b"event: delta" in message.get("body", b"") and not logged_out:
                    result = await client.post("/api/auth/logout", headers=csrf)
                    logged_out.append(result.status_code)

            scope = {
                "type": "http", "asgi": {"version": "3.0", "spec_version": "2.0"}, "http_version": "1.1",
                "method": "POST", "scheme": "https", "path": "/api/copilot/answer/stream",
                "raw_path": b"/api/copilot/answer/stream", "query_string": b"",
                "headers": [
                    (b"host", b"app.example.test"), (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"cookie", f"{copilot_app.AUTH_COOKIE_NAME}={cookie}".encode()),
                    (b"x-csrf-token", csrf["X-CSRF-Token"].encode()),
                ],
                "client": ("127.0.0.1", 12346), "server": ("app.example.test", 443),
            }
            await copilot_app.app(scope, receive, send)
            response = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
            assert logged_out == [200]
            assert b"event: delta" in response
            assert b"event: done" not in response

    run(scenario())
    assert provider.closed


def test_copilot_tables_live_in_host_sqlite(copilot_app):
    with closing(copilot_app._meeting_db()) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "copilot_materials" in tables
