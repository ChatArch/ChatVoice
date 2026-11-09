"""Offline contracts for the Plan ASR route and its binary protocol."""

import gzip
import json
import struct
import asyncio
from unittest.mock import patch

import aiohttp
import pytest

from test_meeting_audio_storage import audio_app


def settings(**overrides):
    from chatvoice.asr_routing import PlanSettings

    values = {
        "CHATVOICE_ASR_PLAN_TRANSPORT": "volcengine-ws",
        "CHATVOICE_ASR_PLAN_BASE": "wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_async",
        "CHATVOICE_ASR_PLAN_API_KEY": "test-only-secret",
        "CHATVOICE_ASR_PLAN_MODEL": "bigmodel",
        "CHATVOICE_ASR_PLAN_RESOURCE_ID": "volc.seedasr.sauc.duration",
        "CHATVOICE_ASR_PLAN_USER_AUDIO_ALLOWED": "1",
    }
    values.update(overrides)
    return PlanSettings.from_mapping(values)


def test_auto_prefers_plan_only_when_allowed_and_not_in_backoff():
    from chatvoice.asr_routing import AsrRouter

    now = [1000.0]
    router = AsrRouter(settings(), clock=lambda: now[0])
    assert router.resolve("auto").actual == "volcengine-plan"
    assert router.status()["plan"]["state"] == "unknown"
    router.mark_failure("entitlement")
    fallback = router.resolve("auto")
    assert fallback.actual == "funasr-gpu"
    assert fallback.fallback_reason == "entitlement"
    with pytest.raises(ValueError, match="entitlement"):
        router.resolve("volcengine-plan")
    now[0] += 301
    assert router.status()["plan"]["state"] == "stale"
    assert router.resolve("auto").actual == "volcengine-plan"
    router.mark_available(speech_verified=False)
    assert router.status()["plan"]["state"] == "healthy"
    assert router.status()["plan"]["speech_verified"] is False


def test_unset_is_auto_fixed_choice_is_preserved_and_config_is_restricted():
    from chatvoice.asr_routing import AsrRouter

    router = AsrRouter(settings(CHATVOICE_ASR_PLAN_USER_AUDIO_ALLOWED="0"))
    assert router.resolve("").selected == "auto"
    assert router.resolve("").actual == "funasr-gpu"
    assert router.resolve("funasr-cpu").actual == "funasr-cpu"
    with pytest.raises(ValueError, match="permission"):
        router.resolve("volcengine-plan")
    invalid = settings(CHATVOICE_ASR_PLAN_BASE="wss://example.test/paid")
    assert AsrRouter(invalid).resolve("auto").actual == "funasr-gpu"


def test_binary_frames_have_sequence_gzip_and_bounded_response_parser():
    from chatvoice.volc_plan_asr import encode_request, encode_audio, parse_response

    request = encode_request(1, "bigmodel")
    assert request[:4] == bytes((0x11, 0x11, 0x11, 0))
    assert struct.unpack(">i", request[4:8])[0] == 1
    body = gzip.decompress(request[12:])
    assert struct.unpack(">I", request[8:12])[0] == len(request[12:])
    assert json.loads(body)["request"]["model_name"] == "bigmodel"
    audio = encode_audio(2, b"\0\0" * 10, last=False)
    terminal = encode_audio(3, b"\0\0", last=True)
    assert audio[1] == 0x21
    assert audio[2] == terminal[2] == 0x01  # raw audio, independently gzip compressed
    assert terminal[1] == 0x23
    assert struct.unpack(">i", terminal[4:8])[0] == -3
    payload = gzip.compress(json.dumps({"result": {"text": "你好"}, "code": 20000000}).encode())
    frame = bytes((0x11, 0x93, 0x11, 0)) + struct.pack(">iI", -3, len(payload)) + payload
    parsed = parse_response(frame)
    assert parsed.text == "你好"
    assert parsed.valid_terminal
    with pytest.raises(ValueError):
        parse_response(frame + b"x" * 200_000)


def test_official_audio_only_frame_is_raw_with_gzip():
    from chatvoice.volc_plan_asr import encode_audio

    frame = encode_audio(1, b"\0\0" * 100, last=True)
    assert frame[2] == 0x01
    assert gzip.decompress(frame[12:]) == b"\0\0" * 100


def test_official_success_code_requires_terminal_result_and_rejects_unknown_code():
    from chatvoice.volc_plan_asr import parse_response

    def response(code, *, terminal=True, result=True):
        body = {"code": code}
        if result:
            body["result"] = {"text": "synthetic speech"}
        payload = json.dumps(body).encode()
        return bytes((0x11, 0x93 if terminal else 0x91, 0x10, 0)) + struct.pack(">iI", -1 if terminal else 1, len(payload)) + payload

    assert parse_response(response(20000000)).valid_terminal
    assert not parse_response(response(20000000, terminal=False)).valid_terminal
    assert not parse_response(response(20000000, result=False)).valid_terminal
    assert not parse_response(response(20000001)).valid_terminal


def test_plan_start_matches_aiohttp_signature_and_refuses_redirects():
    from chatvoice.volc_plan_asr import PlanError, PlanStream

    def response(code, *, terminal=False):
        payload = json.dumps({"code": code, "result": {"text": ""}}).encode()
        return bytes((0x11, 0x93 if terminal else 0x91, 0x10, 0)) + struct.pack(">iI", -2 if terminal else 1, len(payload)) + payload

    class FakeWS:
        def __init__(self):
            self.received = 0

        async def send_bytes(self, data):
            assert isinstance(data, bytes)

        async def receive(self):
            self.received += 1
            return aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, response(20000000, terminal=self.received == 2), "")

        async def close(self):
            pass

    async def opened(*args, **kwargs):
        return FakeWS()

    async def run():
        stream = PlanStream(settings())
        try:
            with patch.object(aiohttp.ClientSession, "ws_connect", autospec=True, side_effect=opened):
                await stream.start()
            await stream.send_pcm(b"\0\0" * 10)
            await stream.finish()
            assert (await stream.receive()).valid_terminal
            assert len(stream.session.trace_configs) == 1
            trace = stream.session.trace_configs[0]
            with pytest.raises(PlanError, match="redirect"):
                await trace.on_request_redirect.send(stream.session, None, None)
        finally:
            await stream.close()

    asyncio.run(run())


def test_public_health_and_probe_security_are_separate(audio_app, monkeypatch):
    import asyncio
    import httpx
    from fastapi import HTTPException
    audio_app._ASR_ROUTER.settings = settings()
    def authenticated(request, *, required=True):
        if request.headers.get("X-Test-Auth") != "yes":
            raise HTTPException(status_code=401, detail="login required")
        return {"user_id": "test-owner"}
    def csrf(request, auth):
        if request.headers.get("X-CSRF-Token") != "test-csrf":
            raise HTTPException(status_code=403, detail="csrf required")
    monkeypatch.setattr(audio_app, "_auth_row", authenticated)
    monkeypatch.setattr(audio_app, "_require_csrf", csrf)

    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url="https://app.example.test") as client:
            public = await client.get("/api/asr/health")
            assert public.status_code == 200
            assert "test-only-secret" not in public.text
            assert (await client.post("/api/asr/health/probe")).status_code == 401
            assert (await client.post("/api/asr/health/probe", headers={"X-Test-Auth": "yes"})).status_code == 403
            headers = {"X-Test-Auth": "yes", "X-CSRF-Token": "test-csrf"}
            called = []
            async def fake_probe():
                called.append(True)
                return {"functional": True, "speech_verified": False}
            monkeypatch.setattr(audio_app, "_probe_plan_asr", fake_probe)
            first = await client.post("/api/asr/health/probe", headers=headers)
            assert first.status_code == 200
            assert called == [True]
            assert first.json()["plan"]["speech_verified"] is False
            assert (await client.post("/api/asr/health/probe", headers=headers)).status_code == 429
    asyncio.run(asyncio.wait_for(flow(), 12))


def test_plan_stream_commit_uses_new_connection_without_replaying_samples(audio_app, monkeypatch):
    import asyncio
    import base64
    from chatvoice.volc_plan_asr import PlanResponse

    audio_app._ASR_ROUTER.settings = settings()
    streams = []
    class FakePlan:
        def __init__(self, *args, **kwargs):
            self.audio = []
            self.events = asyncio.Queue()
            streams.append(self)
        async def start(self):
            return PlanResponse(1, False, "", 0, False)
        async def send_pcm(self, pcm):
            self.audio.append(pcm)
        async def finish(self):
            await self.events.put(PlanResponse(3, True, f"window {len(streams)}", 0, True))
        async def receive(self, *, timeout=15):
            return await self.events.get()
        async def close(self):
            pass
    class Client:
        def __init__(self):
            self.messages = asyncio.Queue()
            self.sent = []
        async def receive(self):
            return await self.messages.get()
        async def send_json(self, payload):
            self.sent.append(payload)
            if payload.get("demo_event") == "asr.stream.done" and not payload.get("final"):
                await self.messages.put({"text": json.dumps({"type": "asr.stream.append", "audio": base64.b64encode(b"\2\0" * 80).decode()})})
                await self.messages.put({"text": json.dumps({"type": "asr.stream.finish"})})
    client = Client()
    monkeypatch.setattr(audio_app, "PlanStream", FakePlan)
    async def flow():
        await client.messages.put({"text": json.dumps({"type": "asr.stream.append", "audio": base64.b64encode(b"\1\0" * 80).decode()})})
        await client.messages.put({"text": json.dumps({"type": "asr.stream.commit"})})
        result = await audio_app._run_plan_stream(client, audio_app.AsrStreamSession(channel="volcengine-plan"), "auto")
        assert result is None
    asyncio.run(asyncio.wait_for(flow(), 4))
    assert [stream.audio for stream in streams] == [[b"\1\0" * 80], [b"\2\0" * 80]]
    results = [message["result"] for message in client.sent if message.get("demo_event") == "asr.stream.result"]
    assert [result["raw_text"] for result in results] == ["window 1", "window 2"]
    assert all(result["stream"]["final"] for result in results)


@pytest.mark.parametrize("action", ["asr.stream.finish", "asr.stream.commit"])
def test_empty_plan_windows_finish_without_opening_provider(audio_app, monkeypatch, action):
    import asyncio

    audio_app._ASR_ROUTER.settings = settings()
    opened = []
    class UnexpectedPlan:
        def __init__(self, *args, **kwargs):
            opened.append(True)
            raise AssertionError("empty Plan window must not open upstream")
    class Client:
        def __init__(self):
            self.messages = asyncio.Queue()
            self.sent = []
        async def receive(self):
            return await self.messages.get()
        async def send_json(self, payload):
            self.sent.append(payload)
    monkeypatch.setattr(audio_app, "PlanStream", UnexpectedPlan)
    client = Client()
    async def flow():
        await client.messages.put({"text": json.dumps({"type": action})})
        if action.endswith("commit"):
            await client.messages.put({"text": json.dumps({"type": "asr.stream.finish"})})
        result = await audio_app._run_plan_stream(client, audio_app.AsrStreamSession(channel="volcengine-plan"), "auto")
        assert result is None
    asyncio.run(asyncio.wait_for(flow(), 3))
    assert opened == []
    done = [event for event in client.sent if event.get("demo_event") == "asr.stream.done"]
    assert done[-1]["final"] is True
    assert [event["final"] for event in done] == ([False, True] if action.endswith("commit") else [True])


def test_plan_finish_failure_recovers_audio_and_stays_final(audio_app, monkeypatch):
    import asyncio
    import base64
    import io
    import wave
    from chatvoice.volc_plan_asr import PlanError, PlanResponse

    audio_app._ASR_ROUTER.settings = settings()
    sample = b"\1\0" * 80
    recovered = []
    sent_pcm = []
    class FailedFinishPlan:
        def __init__(self, *args, **kwargs):
            pass
        async def start(self):
            return PlanResponse(1, False, "", 20000000, False)
        async def send_pcm(self, pcm):
            sent_pcm.append(pcm)
        async def receive(self, *, timeout=15):
            await asyncio.Future()
        async def finish(self):
            raise PlanError("network")
        async def close(self):
            pass
    class Client:
        def __init__(self):
            self.messages = asyncio.Queue()
            self.sent = []
        async def receive(self):
            return await self.messages.get()
        async def send_json(self, payload):
            self.sent.append(payload)
    async def local_result(client, session, index, wav_bytes, final=False):
        assert session.channel == "funasr-gpu" and final
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            recovered.append(wav.readframes(wav.getnframes()))
        await client.send_json({"demo_event": "asr.stream.result", "result": {"raw_text": "recovered", "stream": {"final": final}}})
    monkeypatch.setattr(audio_app, "PlanStream", FailedFinishPlan)
    monkeypatch.setattr(audio_app, "_send_asr_stream_result", local_result)
    client = Client()
    async def flow():
        await client.messages.put({"text": json.dumps({"type": "asr.stream.append", "audio": base64.b64encode(sample).decode()})})
        await client.messages.put({"text": json.dumps({"type": "asr.stream.finish"})})
        return await audio_app._run_plan_stream(client, audio_app.AsrStreamSession(channel="volcengine-plan"), "auto")
    assert asyncio.run(asyncio.wait_for(flow(), 3)) is None
    assert sent_pcm == [sample]
    assert recovered == [sample]
    assert not any(event.get("demo_event") == "asr.stream.started" for event in client.sent)
    assert [event["final"] for event in client.sent if event.get("demo_event") == "asr.stream.done"] == [True]


def test_upload_auto_falls_back_only_before_plan_text(audio_app, monkeypatch):
    from chatvoice.volc_plan_asr import PlanError
    audio_app._ASR_ROUTER.settings = settings()
    def denied(*args):
        raise PlanError("entitlement")
    monkeypatch.setattr(audio_app, "_plan_asr", denied)
    monkeypatch.setattr(audio_app, "_funasr_gpu_asr", lambda *args: audio_app.normalize_asr_result("funasr-gpu", "local text"))
    result = audio_app.transcribe_audio_bytes("auto", b"RIFFfake", "test.wav")
    assert result["channel"] == "funasr-gpu"
    assert result["meta"]["selected_channel"] == "auto"
    assert result["meta"]["fallback_reason"] == "entitlement"
    with pytest.raises(ValueError, match="entitlement"):
        audio_app.transcribe_audio_bytes("volcengine-plan", b"RIFFfake", "test.wav")


def test_live_plan_failure_recovers_only_unconfirmed_audio(audio_app, monkeypatch):
    import asyncio
    import base64
    import io
    import wave
    from chatvoice.volc_plan_asr import PlanError, PlanResponse

    audio_app._ASR_ROUTER.settings = settings()
    sent = []
    recovered = []
    class FailedPlan:
        def __init__(self, *args, **kwargs):
            self.events = asyncio.Queue()
        async def start(self):
            return PlanResponse(1, False, "", 0, False)
        async def send_pcm(self, pcm):
            sent.append(pcm)
            await self.events.put(PlanError("network"))
        async def receive(self, *, timeout=15):
            event = await self.events.get()
            raise event
        async def close(self):
            pass
    class Client:
        def __init__(self):
            self.messages = asyncio.Queue()
            self.sent = []
        async def receive(self):
            return await self.messages.get()
        async def send_json(self, payload):
            self.sent.append(payload)
    async def local_result(client, session, index, wav_bytes, final=False):
        assert session.channel == "funasr-gpu"
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            recovered.append(wav.readframes(wav.getnframes()))
        await client.send_json({"demo_event": "asr.stream.result", "result": {"raw_text": "recovered", "meta": {"fallback_reason": session.fallback_reason}}})
    monkeypatch.setattr(audio_app, "PlanStream", FailedPlan)
    monkeypatch.setattr(audio_app, "_send_asr_stream_result", local_result)
    client = Client()
    sample = b"\1\0" * 80
    async def flow():
        await client.messages.put({"text": json.dumps({"type": "asr.stream.append", "audio": base64.b64encode(sample).decode()})})
        local_session = await audio_app._run_plan_stream(client, audio_app.AsrStreamSession(channel="volcengine-plan"), "auto")
        assert local_session.channel == "funasr-gpu"
    asyncio.run(asyncio.wait_for(flow(), 4))
    assert sent == [sample]
    assert recovered == [sample]
    results = [item["result"] for item in client.sent if item.get("demo_event") == "asr.stream.result"]
    assert results[0]["meta"]["fallback_reason"] == "network"


def test_live_plan_after_text_stops_with_continuation_and_no_local_replay(audio_app, monkeypatch):
    import asyncio
    import base64
    from chatvoice.volc_plan_asr import PlanError, PlanResponse

    audio_app._ASR_ROUTER.settings = settings()
    class FailedAfterText:
        def __init__(self, *args, **kwargs):
            self.calls = 0
        async def start(self):
            return PlanResponse(1, False, "", 0, False)
        async def send_pcm(self, pcm):
            assert pcm == b"\1\0" * 80
        async def receive(self, *, timeout=15):
            self.calls += 1
            if self.calls == 1:
                return PlanResponse(2, False, "cloud text", 0, False)
            raise PlanError("quota")
        async def close(self):
            pass
    class Client:
        def __init__(self):
            self.sent = []
            self.messages = asyncio.Queue()
            self.messages.put_nowait({"text": json.dumps({"type": "asr.stream.append", "audio": base64.b64encode(b"\1\0" * 80).decode()})})
        async def receive(self):
            return await self.messages.get()
        async def send_json(self, payload):
            self.sent.append(payload)
    monkeypatch.setattr(audio_app, "PlanStream", FailedAfterText)
    monkeypatch.setattr(audio_app, "transcribe_audio_bytes", lambda *args: pytest.fail("confirmed cloud text must not replay locally"))
    client = Client()
    result = asyncio.run(asyncio.wait_for(audio_app._run_plan_stream(client, audio_app.AsrStreamSession(channel="volcengine-plan"), "auto"), 4))
    assert result is None
    assert [item["result"]["raw_text"] for item in client.sent if item.get("demo_event") == "asr.stream.result"] == ["cloud text"]
    assert any(item.get("demo_event") == "asr.stream.error" and "新建会议" in item["message"] for item in client.sent)
