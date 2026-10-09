"""Focused, offline red/green coverage for Copilot resource boundaries."""

import asyncio
import io
import sys
import types
import zlib
from pathlib import Path

import pytest
from fastapi import HTTPException

from chatvoice import text_api
from chatvoice.copilot import context, materials
from chatvoice.copilot.materials import MaterialParseError, parse_material_bytes
from chatvoice.web.upload_limits import AudioUploadLimits


def _run(coro):
    return asyncio.run(coro)


async def _limited_request(*, headers, chunks, limit=8, path="/api/copilot/materials"):
    observed = []
    sent = []
    pending = iter(chunks)

    async def receive():
        return next(pending)

    async def downstream(scope, bounded_receive, send):
        observed.append(await bounded_receive())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    limiter = AudioUploadLimits(downstream, limit_for_path=lambda _path: limit)

    async def send(message):
        sent.append(message)

    await limiter(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": headers,
        },
        receive,
        send,
    )
    return observed, sent


def test_material_body_limit_blocks_declared_and_chunked_before_downstream_receive():
    observed, sent = _run(
        _limited_request(
            headers=[(b"content-length", b"9")],
            chunks=[{"type": "http.request", "body": b"x" * 9, "more_body": False}],
        )
    )
    assert observed == []
    assert sent[0]["status"] == 413

    with pytest.raises(HTTPException) as exc:
        _run(
            _limited_request(
                headers=[],
                chunks=[{"type": "http.request", "body": b"x" * 9, "more_body": False}],
            )
        )
    assert exc.value.status_code == 413

    observed, sent = _run(
        _limited_request(
            path="/api/asr",
            headers=[(b"content-length", b"9")],
            chunks=[{"type": "http.request", "body": b"x" * 9, "more_body": False}],
        )
    )
    assert observed == []
    assert sent[0]["status"] == 413


def _flate_pdf(payload: bytes) -> bytes:
    compressed = zlib.compress(payload)
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Length " + str(len(compressed)).encode() + b" /Filter /FlateDecode >>\n"
        b"stream\n" + compressed + b"\nendstream\nendobj\n"
        b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
    )


def _text_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    compressed = zlib.compress(content)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(compressed)).encode() + b" /Filter /FlateDecode >>\nstream\n" + compressed + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode())
        result.extend(value)
        result.extend(b"\nendobj\n")
    xref = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(result)


def test_pdf_preflight_rejects_small_flate_expansion_before_pdfreader(monkeypatch):
    constructed = []

    class UnexpectedPdfReader:
        def __init__(self, *_args, **_kwargs):
            constructed.append(True)
            raise AssertionError("PdfReader must not receive an oversized decoded stream")

    fake_pypdf = types.ModuleType("pypdf")
    fake_pypdf.PdfReader = UnexpectedPdfReader
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)
    monkeypatch.setattr(materials, "PDF_MAX_DECODED_STREAM_BYTES", 64, raising=False)

    with pytest.raises(MaterialParseError) as exc:
        parse_material_bytes("expanded.pdf", _flate_pdf(b"A" * 256), text_cap=500)

    assert exc.value.code == "pdf_expansion_limit"
    assert constructed == []


def test_pdf_preflight_keeps_small_valid_flate_text_pdf_working():
    assert "bounded PDF" in parse_material_bytes("normal.pdf", _text_pdf("bounded PDF"))


def test_pdf_preflight_rejects_unsupported_filter_before_pdfreader(monkeypatch):
    constructed = []

    class UnexpectedPdfReader:
        def __init__(self, *_args, **_kwargs):
            constructed.append(True)

    fake_pypdf = types.ModuleType("pypdf")
    fake_pypdf.PdfReader = UnexpectedPdfReader
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)
    data = b"%PDF-1.4\n1 0 obj\n<< /Length 3 /Filter /LZWDecode >>\nstream\nabc\nendstream\nendobj\n%%EOF\n"
    with pytest.raises(MaterialParseError) as exc:
        parse_material_bytes("unsupported.pdf", data)
    assert exc.value.code == "pdf_stream_unsupported"
    assert constructed == []


def test_pdf_preflight_caps_object_parse_work_before_pdfreader(monkeypatch):
    constructed = []

    class UnexpectedPdfReader:
        def __init__(self, *_args, **_kwargs):
            constructed.append(True)

    fake_pypdf = types.ModuleType("pypdf")
    fake_pypdf.PdfReader = UnexpectedPdfReader
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)
    monkeypatch.setattr(materials, "PDF_MAX_OBJECTS", 2)
    data = b"%PDF-1.4\n" + b"".join(
        f"{index} 0 obj\n<< /Type /Example >>\nendobj\n".encode() for index in range(1, 4)
    ) + b"%%EOF\n"
    with pytest.raises(MaterialParseError) as exc:
        parse_material_bytes("many-objects.pdf", data)
    assert exc.value.code == "pdf_expansion_limit"
    assert constructed == []


def test_retrieval_bounds_segment_and_candidate_work_without_global_sort(monkeypatch):
    calls = []
    original_tokens = context._tokens

    def counted_tokens(value):
        calls.append(value)
        return original_tokens(value)

    monkeypatch.setattr(context, "_tokens", counted_tokens)
    docs = [context.MaterialDocument("m1", "many.txt", "a。\n" * 12)]
    snippets = context.retrieve_material_snippets(
        "a", docs, max_snippets=2, max_segments=3, segment_chars=8,
    )

    assert len(snippets) == 2
    assert len(calls) <= 4  # one query plus at most three bounded segments


def test_retrieval_cap_is_deterministic_and_truncates_late_segments():
    docs = [context.MaterialDocument("m1", "many.txt", "miss。\n" * 3 + "target。")]
    assert context.retrieve_material_snippets("target", docs, max_segments=3) == []
    snippets = context.retrieve_material_snippets("target", docs, max_segments=4)
    assert [(item.source_id, item.score) for item in snippets] == [("m1", 1)]


def test_live_prompt_budget_is_exact_and_rejects_impossible_mandatory_question():
    question = "现在应该如何回复客户？"
    prompt = context.build_live_prompt(
        {
            "meeting_context": "会前背景" * 30,
            "directives": ["保持简短" * 20],
            "documents": [("a.txt", "证据" * 80)],
            "lines": [("客户", "最近转写" * 80)],
        },
        question,
        budget=180,
    )
    assert question in prompt
    assert len(prompt) <= 180

    with pytest.raises(context.ContextBudgetError, match="question"):
        context.build_live_prompt({}, "q" * 80, budget=20)


def test_stream_text_limits_bound_input_and_close_response(monkeypatch):
    response = io.BytesIO(b"data: " + b"x" * 128 + b"\n")
    payloads = []

    def fake_open(request, timeout):
        payloads.append((request, timeout))
        return response

    monkeypatch.setattr(text_api, "_open_request", fake_open)
    settings = text_api.TextSettings("https://offline.example.test/v1", "secret", "offline")
    with pytest.raises(text_api.TextRequestError, match="configured limit"):
        list(text_api.stream_text(
            settings,
            [{"role": "user", "content": "hello"}],
            max_tokens=17,
            max_line_bytes=32,
            max_stream_bytes=64,
            max_events=2,
            max_output_chars=16,
            max_output_bytes=32,
        ))

    assert response.closed
    request, timeout = payloads[0]
    assert timeout > 0
    assert b'"max_tokens": 17' in request.data


def test_stream_text_rejects_elapsed_deadline_before_opening_provider(monkeypatch):
    called = []
    monkeypatch.setattr(text_api, "_open_request", lambda *_args: called.append(True))
    settings = text_api.TextSettings("https://offline.example.test/v1", "secret", "offline")
    with pytest.raises(text_api.TextRequestError, match="deadline"):
        next(text_api.stream_text(
            settings,
            [{"role": "user", "content": "hello"}],
            deadline=0,
        ))
    assert called == []


def test_stream_text_rejects_valid_delta_that_exceeds_output_budget(monkeypatch):
    body = b'data: {"choices": [{"delta": {"content": "abcdef"}}]}\n\ndata: [DONE]\n'
    response = io.BytesIO(body)
    monkeypatch.setattr(text_api, "_open_request", lambda *_args, **_kwargs: response)
    settings = text_api.TextSettings("https://offline.example.test/v1", "secret", "offline")
    with pytest.raises(text_api.TextRequestError, match="configured limit"):
        list(text_api.stream_text(settings, [{"role": "user", "content": "hello"}], max_output_chars=5))
    assert response.closed


def test_stream_text_checks_cancellation_while_reading_a_trickled_line(monkeypatch):
    class OneByteResponse:
        def __init__(self):
            self.reads = 0
            self.closed = False

        def read(self, _size):
            self.reads += 1
            return b"d"

        def close(self):
            self.closed = True

    response = OneByteResponse()
    monkeypatch.setattr(text_api, "_open_request", lambda *_args, **_kwargs: response)
    checks = []

    def active():
        checks.append(True)
        return len(checks) < 4

    settings = text_api.TextSettings("https://offline.example.test/v1", "secret", "offline")
    with pytest.raises(text_api.TextRequestError, match="cancelled"):
        list(text_api.stream_text(
            settings,
            [{"role": "user", "content": "hello"}],
            max_line_bytes=32,
            should_continue=active,
        ))
    assert response.reads == 1
    assert response.closed


def test_copilot_tab_initializes_status_and_materials_on_normal_entry():
    page = Path("src/chatvoice/web/static/index.html").read_text(encoding="utf-8")
    handler = page.rsplit("document.querySelectorAll('.product-tab')", 1)[1].split("$('voice-options')", 1)[0]
    assert "button.dataset.product === 'copilot'" in handler
    assert "showCopilotPage()" in handler
