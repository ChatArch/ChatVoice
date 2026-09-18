"""Offline regressions for Copilot backend review blockers."""
import asyncio
import io
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
from zipfile import ZipFile, ZIP_DEFLATED

import httpx
import pytest
from test_copilot_routes import copilot_app, _login, run
from chatvoice import text_api
from chatvoice.copilot import context, materials


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("Real network forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def zipped(entries):
    out = io.BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return out.getvalue()


@pytest.mark.parametrize("data", [b"not zip", zipped([("other.xml", "x")]), zipped([("word/document.xml", "<bad")])])
def test_docx_errors_are_safe(data):
    with pytest.raises(materials.MaterialParseError) as err:
        materials.parse_material_bytes("bad.docx", data)
    assert err.value.status_code == 422


@pytest.mark.parametrize("entries", [
    [("word/document.xml", "x" * 2_000_001)],
    [("word/document.xml", "<x/>")] + [(f"f{i}", "") for i in range(256)],
    [("word/document.xml", "<x/>"), ("huge", "x" * 8_000_001)],
    [("word/document.xml", "<x/>")] + [(f"f{i}", "x" * 6_000_000) for i in range(3)],
])
def test_docx_expansion_rejected_before_parser(monkeypatch, entries):
    import docx
    def forbidden(*a, **k):
        pytest.fail("Document parser must not run before ZIP size checks")
    monkeypatch.setattr(docx, "Document", forbidden)
    with pytest.raises(materials.MaterialParseError) as err:
        materials.parse_material_bytes("bomb.docx", zipped(entries))
    assert err.value.status_code == 413


def test_valid_docx():
    from docx import Document
    doc = Document()
    doc.add_paragraph("合法正文")
    out = io.BytesIO()
    doc.save(out)
    assert materials.parse_material_bytes("valid.docx", out.getvalue()) == "合法正文"


def test_docx_fallback_reads_xml_without_password_argument(monkeypatch):
    monkeypatch.setitem(sys.modules, "docx", None)
    xml = '<w:document xmlns:w="urn:w"><w:t>正文</w:t></w:document>'
    assert materials.parse_material_bytes("fallback.docx", zipped([("word/document.xml", xml)])) == "正文"


def test_pdf_page_limit_is_rejection(monkeypatch):
    class Page:
        def extract_text(self):
            pytest.fail("Do not extract over-page PDF")
    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda *a, **k: SimpleNamespace(pages=[Page(), Page()])))
    with pytest.raises(materials.MaterialParseError) as err:
        materials.parse_material_bytes("large.pdf", b"%PDF", page_cap=1)
    assert err.value.status_code == 413


@pytest.mark.parametrize("suffix", ["txt", "pdf"])
def test_text_limit_rejects_instead_of_clipping(monkeypatch, suffix):
    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda *a, **k: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "x" * 21)])))
    with pytest.raises(materials.MaterialParseError) as err:
        materials.parse_material_bytes("large." + suffix, b"x" * 21, text_cap=20)
    assert err.value.status_code == 413


def test_recent_long_line_keeps_tail():
    result = context._transcript_block([("speaker", "x" * 5000 + "LATEST-ANSWER")], 100)
    assert result.endswith("LATEST-ANSWER")
    assert context.TRUNCATION_MARKER in result
    assert len(result) <= 100


def test_copilot_serves_real_app(copilot_app):
    response = copilot_app.copilot_page()
    assert Path(response.path) == copilot_app.STATIC_DIR / "index.html"


def test_upload_read_is_bounded(copilot_app, monkeypatch):
    class Upload:
        filename = "huge.txt"
        async def read(self, size=-1):
            assert size == copilot_app.MAX_COPILOT_MATERIAL_BYTES + 1
            return b"x" * size
    monkeypatch.setattr(copilot_app, "_auth_row", lambda request: {"user_id": "test"})
    monkeypatch.setattr(copilot_app, "_require_csrf", lambda *a: None)
    with pytest.raises(copilot_app.HTTPException) as err:
        run(copilot_app.copilot_upload_material(None, Upload()))
    assert err.value.status_code == 413


@pytest.mark.parametrize("value,outcome", [("missing", {}), ("empty", {}), ("broken", ValueError("sensitive")), (" ", {})])
def test_explicit_profile_fails_closed(copilot_app, monkeypatch, value, outcome):
    monkeypatch.setenv("CHATVOICE_ENV_PROFILE", value)
    def load(*a):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(copilot_app.EnvStore, "load_profile", load)
    monkeypatch.setattr(copilot_app.EnvStore, "load_active", lambda *a: pytest.fail("No active fallback"))
    with pytest.raises(RuntimeError, match="CHATVOICE_ENV_PROFILE") as err:
        copilot_app._load_chatvoice_env_values()
    assert "sensitive" not in str(err.value)


def test_real_missing_named_profile_fails_closed(copilot_app, monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "isolated-chatarch"))
    monkeypatch.setenv("CHATVOICE_ENV_PROFILE", "does-not-exist")
    with pytest.raises(RuntimeError, match="CHATVOICE_ENV_PROFILE"):
        copilot_app._load_chatvoice_env_values()


@pytest.mark.parametrize("mode", ["provider-default", "ark-disabled"])
def test_copilot_thinking_payload_scoped(copilot_app, monkeypatch, mode):
    monkeypatch.setattr(copilot_app, "COPILOT_THINKING_MODE", mode)
    monkeypatch.setattr(copilot_app, "_copilot_messages", lambda *a: ([{"role": "user", "content": "synthetic"}], [], 0))
    calls = []
    def opened(req, timeout):
        calls.append(json.loads(req.data))
        return io.BytesIO(b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n')
    monkeypatch.setattr(text_api, "_open_request", opened)
    list(copilot_app._copilot_answer_stream(copilot_app.CopilotAnswerRequest(question="synthetic", request_id="offline-test"), "test"))
    assert len(calls) == 1
    assert calls[0].get("thinking") == ({"type": "disabled"} if mode == "ark-disabled" else None)
    settings = text_api.TextSettings("https://example.test/v1", "offline", "model")
    assert "thinking" not in json.loads(text_api._request(settings, []).data)


def test_unknown_thinking_fails_before_network(copilot_app, monkeypatch):
    monkeypatch.setattr(copilot_app, "COPILOT_THINKING_MODE", "typo")
    monkeypatch.setattr(copilot_app, "_copilot_messages", lambda *a: ([], [], 0))
    monkeypatch.setattr(text_api, "_open_request", lambda *a, **k: pytest.fail("Unknown mode must never call model"))
    out = "".join(copilot_app._copilot_answer_stream(copilot_app.CopilotAnswerRequest(question="synthetic", request_id="offline-test"), "test"))
    assert "event: error" in out and "event: done" not in out


def test_notice_has_complete_mit_and_wheel_configuration():
    root = Path(__file__).resolve().parents[1]
    notice = (root / "third_party/Backchannel-COPILOT-NOTICE.md").read_text()
    assert "https://github.com/talberthoule/backchannel" in notice
    assert "16028a55dbbf886b68eaddc06dfd7c38b72de596" in notice
    assert "Copyright (c) 2026 Talbert Houle" in notice
    assert "Permission is hereby granted, free of charge" in notice
    assert "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE." in notice
    pyproject = (root / "pyproject.toml").read_text()
    assert 'license-files = ["LICENSE", "third_party/Backchannel-COPILOT-NOTICE.md"]' in pyproject


def test_malformed_docx_upload_4xx(copilot_app):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=copilot_app.app), base_url="https://app.example.test") as client:
            csrf = await _login(client, copilot_app, "docx@example.test")
            response = await client.post("/api/copilot/materials", headers=csrf, files={"file": ("bad.docx", b"not zip", "application/octet-stream")})
            assert response.status_code == 422
            assert response.json()["detail"]["code"] == "invalid_docx"
    run(scenario())
