"""Supervisor regressions for review findings, with real ASGI scheduling."""
import asyncio
import io
import json
from pathlib import Path
import threading
import time
import zlib

import httpx
import pytest
from chatvoice import text_api
from chatvoice.copilot import materials
from test_copilot_routes import copilot_app, _login, run


def pdf_stream(metadata, payload=b"A" * 256):
    raw = zlib.compress(payload)
    return (b"%PDF-1.4\n1 0 obj\n<< /Length " + str(len(raw)).encode()
            + b" " + metadata + b">>\nstream\n" + raw
            + b"\nendstream\nendobj\n%%EOF\n")


@pytest.mark.parametrize("metadata", [b"/F#69lter /FlateDecode", b"/F#69lter [/Fl#61teDecode]"])
def test_pdf_escaped_names_cannot_bypass_decoded_cap(monkeypatch, metadata):
    monkeypatch.setattr(materials, "PDF_MAX_DECODED_STREAM_BYTES", 64)
    with pytest.raises(materials.MaterialParseError) as exc:
        materials._preflight_pdf_streams(pdf_stream(metadata))
    assert exc.value.code in {"pdf_expansion_limit", "pdf_stream_unsupported"}


@pytest.mark.parametrize("metadata", [b"/Type /ObjStm /Filter /FlateDecode", b"/#54ype /XRef /Filter /FlateDecode"])
def test_pdf_hidden_object_or_xref_layout_is_rejected_before_reader(metadata):
    with pytest.raises(materials.MaterialParseError) as exc:
        materials._preflight_pdf_streams(pdf_stream(metadata, b"small"))
    assert exc.value.code == "pdf_stream_unsupported"


@pytest.mark.parametrize("metadata", [
    b"/Type /XObject /Subtype /Form /Filter /FlateDecode",
    b"/Filter /FlateDecode /DecodeParms << /Predictor 12 /Columns 1000000 >>",
])
def test_pdf_recursive_forms_and_unvalidated_decode_parameters_fail_closed(metadata):
    with pytest.raises(materials.MaterialParseError) as exc:
        materials._preflight_pdf_streams(pdf_stream(metadata, b"small"))
    assert exc.value.code == "pdf_stream_unsupported"


def test_pdf_nested_direct_stream_cannot_hide_from_preflight():
    raw = zlib.compress(b"A" * 256).hex().encode() + b">"
    nested = (b"%PDF-1.4\n1 0 obj\n<< /Nested << /Length " + str(len(raw)).encode()
        + b" /Filter [/ASCIIHexDecode /FlateDecode] >>\nstream\n" + raw
        + b"\nendstream\n>>\nendobj\n%%EOF\n")
    with pytest.raises(materials.MaterialParseError) as exc:
        materials._preflight_pdf_streams(nested)
    assert exc.value.code == "pdf_stream_unsupported"


def test_pdf_numeric_length_abuse_is_a_controlled_parse_error():
    blob = b"%PDF-1.4\n1 0 obj\n<< /Length " + b"9" * 5000 + b">>\nstream\nx\nendstream\nendobj\n%%EOF\n"
    with pytest.raises(materials.MaterialParseError):
        materials._preflight_pdf_streams(blob)


def test_pdf_reader_dependency_floor_matches_used_public_constructor():
    # The bounded recovery constructor was verified on 6.19.0; older retained
    # installs must not turn valid PDFs into misleading OCR errors.
    project = Path(__file__).resolve().parents[1] / "pyproject.toml"
    assert "pypdf>=6.19,<7.0" in project.read_text()


@pytest.mark.parametrize("path", ["/api/copilot/answer/stream", "/api/copilot/prepare"])
def test_copilot_json_body_is_bounded_before_model_parsing(path):
    from test_copilot_resource_bounds import _limited_request
    observed, sent = run(_limited_request(path=path, headers=[(b"content-length", b"9")],
        chunks=[{"type": "http.request", "body": b"x" * 9, "more_body": False}]))
    assert not observed
    assert sent[0]["status"] == 413


def test_sse_cancellation_on_terminal_newline_never_completes(monkeypatch):
    invalid = [False]
    first = ("data: " + json.dumps({"choices": [{"delta": {"content": "synthetic"}}]}) + "\n").encode()

    class InvalidatingRead(io.BytesIO):
        def read(self, size=-1):
            value = super().read(size)
            if self.tell() == len(first) + len(b"data: [DONE]\n"):
                invalid[0] = True
            return value

    response = InvalidatingRead(first + b"data: [DONE]\n")
    monkeypatch.setattr(text_api, "_open_request", lambda *_a, **_k: response)
    with pytest.raises(text_api.TextRequestError, match="cancelled"):
        list(text_api.stream_text(text_api.TextSettings("https://fixture.example.test/v1", "fixture", "fixture"),
             [{"role": "user", "content": "synthetic"}], max_line_bytes=1024,
             should_continue=lambda: not invalid[0]))
    assert response.closed


@pytest.mark.parametrize("action", ["disconnect", "logout"])
def test_invalidation_while_provider_waits_is_observed_before_next_delta(copilot_app, monkeypatch, action):
    entered = threading.Event()

    class WaitingProvider:
        closed = False
        saw_invalidation = False
        steps = 0
        continuation = None

        def __iter__(self):
            return self

        def __next__(self):
            self.steps += 1
            if self.steps == 1:
                return "first"
            entered.set()
            # Every boundary is finite; no stuck test thread or process signals.
            for _ in range(40):
                if not self.continuation():
                    self.saw_invalidation = True
                    raise text_api.TextRequestError("cancelled")
                time.sleep(.005)
            raise StopIteration

        def close(self):
            self.closed = True

    provider = WaitingProvider()

    def open_provider(*_args, **kwargs):
        provider.continuation = kwargs["should_continue"]
        return provider

    monkeypatch.setattr(text_api, "stream_text", open_provider)

    async def scenario():
        transport = httpx.ASGITransport(app=copilot_app.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://app.example.test") as client:
            csrf = await _login(client, copilot_app, "waiting@example.test")
            cookie = client.cookies.get(copilot_app.AUTH_COOKIE_NAME)
            body = json.dumps({"question": "synthetic?", "request_id": "waiting-case"}).encode()
            delivered = [False]
            acted = [False]
            sent = []

            async def receive():
                if not delivered[0]:
                    delivered[0] = True
                    return {"type": "http.request", "body": body, "more_body": False}
                while not entered.is_set():
                    await asyncio.sleep(.001)
                if action == "disconnect":
                    return {"type": "http.disconnect"}
                if not acted[0]:
                    acted[0] = True
                    assert (await client.post("/api/auth/logout", headers=csrf)).status_code == 200
                await asyncio.Event().wait()

            async def send(message):
                sent.append(message)

            scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.0"},
                "http_version": "1.1", "method": "POST", "scheme": "https",
                "path": "/api/copilot/answer/stream", "raw_path": b"/api/copilot/answer/stream", "query_string": b"",
                "headers": [(b"host", b"app.example.test"), (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"cookie", f"{copilot_app.AUTH_COOKIE_NAME}={cookie}".encode()),
                    (b"x-csrf-token", csrf["X-CSRF-Token"].encode())],
                "client": ("127.0.0.1", 12345), "server": ("app.example.test", 443)}
            await copilot_app.app(scope, receive, send)
            output = b"".join(m.get("body", b"") for m in sent)
            assert b"event: done" not in output
            assert provider.closed
            assert provider.saw_invalidation, "Invalidation must be observed while provider waits, not only after it returns"

    run(scenario())
