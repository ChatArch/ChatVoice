"""Copilot context assembly and material parsing are deterministic and bounded."""

import pytest
from chatvoice.copilot import context
from chatvoice.copilot.materials import MaterialParseError, parse_material_bytes


def test_live_prompt_keeps_recent_transcript_and_marks_omission():
    prompt = context.build_live_prompt(
        {
            "meeting_context": "客户关注迁移冻结。",
            "directives": ["先给中文短答"],
            "documents": [("方案.md", "企业版支持 SSO。")],
            "lines": [("早期", "x" * 4000), ("客户", "预算是 18 万，周四前确认。")],
        },
        "预算和时间点是什么？",
        budget=900,
    )
    assert "预算是 18 万" in prompt
    assert context.TRUNCATION_MARKER in prompt
    assert "untrusted evidence" in context.LIVE_SYSTEM_PROMPT


def test_lexical_retrieval_handles_chinese_and_caps_snippets():
    docs = [
        context.MaterialDocument("m1", "价格方案.md", "企业版价格 18 万，包含 SSO 和审计日志。\n\n实施周期两周。"),
        context.MaterialDocument("m2", "安全.txt", "权限模型支持最小权限和审计。"),
    ]
    snippets = context.retrieve_material_snippets("SSO 价格是多少", docs, max_snippets=2, snippet_chars=28)
    assert [item.source_id for item in snippets][:1] == ["m1"]
    assert all(len(item.text) <= 28 for item in snippets)
    evidence = context.format_evidence(snippets)
    assert "[1] 价格方案.md" in evidence
    assert "retrieved context" in evidence


def test_parse_text_markdown_pdf_no_text_and_caps():
    assert parse_material_bytes("a.txt", "第一段\n\n第二段".encode()) == "第一段\n\n第二段"
    assert parse_material_bytes("a.md", "# 标题\n\n- **要点**".encode()) == "标题\n\n要点"
    with pytest.raises(MaterialParseError) as exc:
        parse_material_bytes("large.txt", ("字" * 200).encode(), text_cap=20)
    assert exc.value.status_code == 413
    try:
        parse_material_bytes("scan.pdf", b"%PDF-1.4\n%%EOF")
    except MaterialParseError as exc:
        assert exc.code == "ocr_not_supported"
        assert "OCR" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("empty PDF should fail clearly")
