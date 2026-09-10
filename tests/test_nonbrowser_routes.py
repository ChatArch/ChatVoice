"""Offline ASGI routes: isolated persistence and deterministic upstream boundaries."""
import asyncio
from contextlib import closing
import importlib
import io
import json
import socket
import sys

import httpx
import pytest
import fastapi.routing
import starlette.responses

from test_api_tokens import _sample_meeting_payload, _sample_conversation_payload


@pytest.fixture
def flows_app(monkeypatch, tmp_path):
    monkeypatch.setattr(socket.socket, "connect", lambda *args, **kwargs: pytest.fail("Real network forbidden"))
    async def deterministic_executor(function, *args, **kwargs):
        return function(*args, **kwargs)
    async def deterministic_iterator(iterator):
        for item in iterator:
            yield item
    monkeypatch.setattr(fastapi.routing, "run_in_threadpool", deterministic_executor)
    monkeypatch.setattr(asyncio, "to_thread", deterministic_executor)
    monkeypatch.setattr(starlette.responses, "iterate_in_threadpool", deterministic_iterator)
    for name in ("HOME", "CHATARCH_HOME", "CHATVOICE_HOME"):
        monkeypatch.setenv(name, str(tmp_path / name.lower()))
    monkeypatch.setenv("CHATVOICE_ASR_PREWARM", "0")
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")
    for purpose in ("NOTES", "TITLE"):
        for field, value in {"API_BASE": "https://text.example.test/v1", "API_KEY": "offline-placeholder", "MODEL": "offline-model"}.items():
            monkeypatch.setenv(f"CHATVOICE_MEETING_{purpose}_{field}", value)
    name = "chatvoice.web.legacy_app"
    sys.modules.pop(name, None)
    module = importlib.import_module(name)
    monkeypatch.setattr(module, "MEETING_DB_PATH", tmp_path / "flows.sqlite3")
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("Real network forbidden"))
    yield module
    sys.modules.pop(name, None)


def run_flow(coroutine):
    return asyncio.run(asyncio.wait_for(coroutine, timeout=12))


@pytest.mark.parametrize("route,body", [
    ("/api/meeting-notes/polish", {"transcript": "synthetic"}),
    ("/api/meeting-title", {"transcript": "synthetic"}),
    ("/api/meeting-notes/revise/stream", {"transcript": "synthetic", "current_summary": "original", "instruction": "shorten"}),
])
@pytest.mark.parametrize("mode", ["success", "error", "truncated"])
def test_text_routes_finish_and_failure(flows_app, monkeypatch, route, body, mode):
    from chatvoice import text_api
    responses = []
    def open_request(request, timeout):
        payload = json.loads(request.data)
        assert payload["model"] == "offline-model"
        if mode == "error":
            raise TimeoutError("offline timeout")
        if payload.get("stream"):
            content = 'data: ' + json.dumps({"choices": [{"delta": {"content": "[[[CANVAS]]]synthetic[[[REPLY]]]done"}}]}) + '\n\n'
            if mode == "success":
                content += 'data: [DONE]\n\n'
        else:
            content = json.dumps({"choices": [{"message": {"content": "synthetic result"}, "finish_reason": "stop" if mode == "success" else "length"}]})
        result = io.BytesIO(content.encode())
        responses.append(result)
        return result
    monkeypatch.setattr(text_api, "_open_request", open_request)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=flows_app.app), base_url="https://app.example.test") as client:
            result = await client.post(route, json=body)
            if "stream" in route:
                assert result.status_code == 200
                if mode == "success":
                    assert "event: done" in result.text and "synthetic" in result.text
                    assert "event: error" not in result.text
                else:
                    assert "event: error" in result.text
                    assert "event: done" not in result.text
            elif mode == "success":
                assert result.status_code == 200
                assert result.json().get("content", result.json().get("title")) == "synthetic result"
            else:
                assert result.status_code in (502, 504)
            assert all(response.closed for response in responses)
    run_flow(scenario())


async def login(client, module, account):
    module.provision_managed_account(account, "offline-password", account)
    result = await client.post("/api/auth/login", json={"account": account, "password": "offline-password"})
    assert result.status_code == 200, result.text
    return {"X-CSRF-Token": result.json()["csrf_token"]}


@pytest.mark.parametrize("kind,payload", [("meetings", _sample_meeting_payload()), ("conversations", _sample_conversation_payload())])
def test_account_record_token_session_lifecycle(flows_app, kind, payload):
    async def scenario():
        transport = httpx.ASGITransport(app=flows_app.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://app.example.test") as owner, httpx.AsyncClient(transport=transport, base_url="https://app.example.test") as other:
            route = f"/api/{kind}/offline-record"
            assert (await owner.get(route)).status_code == 401
            assert (await owner.get("/api/auth/session")).json() == {"authenticated": False}
            assert (await owner.post("/api/auth/login", json={"account": "unknown", "password": "bad-password"})).status_code == 401
            csrf = await login(owner, flows_app, "owner@example.test")
            other_csrf = await login(other, flows_app, "other@example.test")
            assert (await owner.put(route, json=payload)).status_code == 403
            assert (await owner.put(route, json=payload, headers=csrf)).status_code == 200
            assert (await owner.get(route)).json()["title"] == payload["title"]
            assert len((await owner.get(f"/api/{kind}")).json()[kind]) == 1
            assert (await other.get(route)).status_code == 404
            assert (await other.get(f"/api/{kind}")).json()[kind] == []
            await other.delete(route, headers=other_csrf)
            assert (await owner.get(route)).status_code == 200
            created = await owner.post("/api/tokens", headers=csrf, json={"name": "offline", "scopes": [f"read:{kind}"]})
            assert created.status_code == 200
            token = created.json()["token"]
            token_id = created.json()["token_info"]["id"]
            assert token not in (await owner.get("/api/tokens")).text
            auth = {"Authorization": f"Bearer {token}"}
            assert (await other.get(f"/api/data/{kind}/offline-record", headers=auth)).json()["title"] == payload["title"]
            assert (await owner.delete(f"/api/tokens/{token_id}", headers=csrf)).status_code == 200
            assert (await other.get(f"/api/data/{kind}/offline-record", headers=auth)).status_code == 401
            assert (await owner.delete(route, headers=csrf)).status_code == 200
            assert (await owner.get(route)).status_code == 404
            assert (await owner.post("/api/auth/logout")).status_code == 403
            assert (await owner.post("/api/auth/logout", headers=csrf)).status_code == 200
            assert (await owner.get("/api/auth/session")).json() == {"authenticated": False}
            with closing(flows_app._meeting_db()) as database:
                database.execute("UPDATE auth_sessions SET expires_at = ?", ("2000-01-01T00:00:00+00:00",))
                database.commit()
            assert (await other.get(f"/api/{kind}")).status_code == 401
            assert (await other.get("/api/auth/session")).json() == {"authenticated": False}
    run_flow(scenario())


@pytest.mark.parametrize("mode", ["success", "empty", "too_large", "upstream_invalid", "failed"])
def test_clone_routes_lifecycle(flows_app, monkeypatch, mode):
    jobs = {}
    def request(method, route, body=None, content_type=None):
        if method == "DELETE":
            jobs.pop("offline", None)
            return {"deleted": True}
        if mode == "upstream_invalid":
            raise flows_app.HTTPException(status_code=422, detail="invalid audio")
        assert b"reference_audio" in body and b"synthetic" in body
        jobs["offline"] = {"job_id": "offline", "status": "failed" if mode == "failed" else "ready"}
        return jobs["offline"]
    monkeypatch.setattr(flows_app, "_voiceclone_request_json", request)
    monkeypatch.setattr(flows_app, "_voiceclone_get_json", lambda route: jobs["offline"])
    monkeypatch.setattr(flows_app, "_voiceclone_get_audio", lambda route: (b"RIFFsynthetic", "audio/wav"))
    monkeypatch.setattr(flows_app, "MAX_VOICECLONE_REFERENCE_BYTES", 32)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=flows_app.app), base_url="https://app.example.test") as client:
            reference = b"" if mode == "empty" else b"x" * 33 if mode == "too_large" else b"synthetic"
            files = {"reference_audio": ("reference.wav", reference, "audio/wav")}
            assert (await client.post("/api/voice-clone/jobs", data={"text": "synthetic"}, files=files)).status_code == 401
            csrf = await login(client, flows_app, "clone@example.test")
            assert (await client.post("/api/voice-clone/jobs", data={"text": "synthetic"}, files=files)).status_code == 403
            result = await client.post("/api/voice-clone/jobs", data={"text": "synthetic"}, files=files, headers=csrf)
            expected = {"empty": 400, "too_large": 413, "upstream_invalid": 422}.get(mode, 202)
            assert result.status_code == expected, result.text
            if expected != 202:
                assert jobs == {}
                return
            status = await client.get("/api/voice-clone/jobs/offline")
            assert status.json()["status"] == jobs["offline"]["status"]
            if mode == "success":
                sound = await client.get("/api/voice-clone/jobs/offline/audio")
                assert sound.content == b"RIFFsynthetic"
                assert "voiceclone-offline.wav" in sound.headers["content-disposition"]
            assert (await client.delete("/api/voice-clone/jobs/offline")).status_code == 403
            assert (await client.delete("/api/voice-clone/jobs/offline", headers=csrf)).status_code == 200
            assert jobs == {}
    run_flow(scenario())


@pytest.mark.parametrize("mode", ["success", "invalid_model", "connect_failure"])
def test_realtime_asgi_protocol_and_cleanup(flows_app, monkeypatch, mode):
    async def scenario():
        incoming = asyncio.Queue()
        await incoming.put({"type": "websocket.connect"})
        outgoing = []
        forwarded = []
        upstream_events = asyncio.Queue()
        closed = []
        class Upstream:
            def __aiter__(self):
                return self
            async def __anext__(self):
                return await upstream_events.get()
            async def send(self, data):
                forwarded.append(data)
            async def close(self):
                closed.append(True)
        async def connect(*args):
            if mode == "connect_failure":
                raise RuntimeError("offline connect failure")
            return Upstream()
        monkeypatch.setattr(flows_app, "_connect_upstream", connect)
        monkeypatch.setattr(flows_app, "_token_plan_key", lambda: "offline-placeholder")
        async def send(message):
            outgoing.append(message)
        model = "invalid" if mode == "invalid_model" else flows_app.REALTIME_MODEL
        scope = {"type": "websocket", "path": "/ws/realtime", "raw_path": b"/ws/realtime", "query_string": f"model={model}".encode(), "headers": [], "scheme": "wss", "client": ("offline", 1), "server": ("app.example.test", 443), "subprotocols": [], "root_path": ""}
        task = asyncio.create_task(flows_app.app(scope, incoming.get, send))
        async def until(predicate):
            for _ in range(200):
                if predicate():
                    return
                await asyncio.sleep(0)
            pytest.fail("ASGI protocol barrier not reached")
        def events():
            return [json.loads(item["text"]) for item in outgoing if item.get("text")]
        try:
            if mode != "success":
                await task
                assert any(event["demo_event"] == "proxy.error" for event in events())
                assert outgoing[-1]["type"] == "websocket.close"
                return
            await until(lambda: any(event["demo_event"] == "proxy.connected" for event in events()))
            for event in [{"type": "session.created", "session": {"id": "offline"}}, {"type": "response.text.delta", "delta": "synthetic"}, {"type": "response.audio.delta", "delta": "AAABAA=="}]:
                await upstream_events.put(json.dumps(event))
            await until(lambda: any(event["demo_event"] == "audio.delta" for event in events()))
            assert any(event.get("event", {}).get("type") == "session.created" for event in events()), "session.created must not be lost"
            assert any(event.get("text") == "synthetic" and event["demo_event"] == "transcript.delta" for event in events())
            await incoming.put({"type": "websocket.receive", "text": '{"type":"input_audio_buffer.append","audio":"AAAA"}'})
            await until(lambda: bool(forwarded))
            assert json.loads(forwarded[0])["audio"] == "AAAA"
            await incoming.put({"type": "websocket.disconnect", "code": 1000})
            await task
            assert closed == [True]
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    run_flow(scenario())
