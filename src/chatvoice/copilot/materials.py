"""Bounded material parsing; excessive inputs are rejected, never clipped."""
from __future__ import annotations

import io
import re
from zipfile import ZipFile
from xml.etree import ElementTree

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx"}
DEFAULT_TEXT_CAP = 120_000
DOCX_MAX_ENTRIES = 256
DOCX_MAX_COMPRESSED_BYTES = 2 * 1024 * 1024
DOCX_MAX_TOTAL_BYTES = 16_000_000
DOCX_MAX_ENTRY_BYTES = 8_000_000
DOCX_MAX_DOCUMENT_BYTES = 2_000_000


class MaterialParseError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _clean_text(value: str) -> str:
    value = value.replace("\x00", "")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _parse_markdown(text: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[ \t]*[-*+]\s+", "", text, flags=re.MULTILINE)
    return text


def _parse_pdf(data: bytes, page_cap: int, text_cap: int) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise MaterialParseError("pdf_dependency_missing", "PDF 解析依赖未安装，请安装 web 可选依赖 pypdf。", status_code=503) from exc
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if len(reader.pages) > page_cap:
            raise MaterialParseError("pdf_page_limit", "PDF 页数超过上限，请拆分材料后上传。", status_code=413)
        texts = []
        size = 0
        for page in reader.pages:
            text = _clean_text(page.extract_text() or "")
            size += len(text) + (2 if texts else 0)
            if size > text_cap:
                raise MaterialParseError("text_limit", "材料文本超过上限，请拆分材料后上传。", status_code=413)
            texts.append(text)
    except MaterialParseError:
        raise
    except Exception as exc:
        if data.lstrip().startswith(b"%PDF"):
            raise MaterialParseError("ocr_not_supported", "PDF 未包含可提取文本；当前不支持 OCR，请上传文字版 PDF 或文本材料。") from exc
        raise MaterialParseError("invalid_pdf", "PDF 文件无法解析。") from exc
    text = _clean_text("\n\n".join(texts))
    if not text:
        raise MaterialParseError("ocr_not_supported", "PDF 未包含可提取文本；当前不支持 OCR，请上传文字版 PDF 或文本材料。")
    return text


def _parse_docx(data: bytes) -> str:
    try:
        if len(data) > DOCX_MAX_COMPRESSED_BYTES:
            raise MaterialParseError("docx_expansion_limit", "DOCX 大小超过上限。", status_code=413)
        with ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if (len(entries) > DOCX_MAX_ENTRIES
                    or sum(item.file_size for item in entries) > DOCX_MAX_TOTAL_BYTES
                    or sum(item.compress_size for item in entries) > DOCX_MAX_COMPRESSED_BYTES
                    or any(item.file_size > DOCX_MAX_ENTRY_BYTES for item in entries)):
                raise MaterialParseError("docx_expansion_limit", "DOCX 解压大小或文件数量超过上限。", status_code=413)
            names = [item.filename for item in entries]
            if len(set(names)) != len(names) or any(item.flag_bits & 1 for item in entries):
                raise MaterialParseError("invalid_docx", "DOCX 包含重复或加密文件。")
            entry = archive.getinfo("word/document.xml")
            if entry.file_size > DOCX_MAX_DOCUMENT_BYTES:
                raise MaterialParseError("docx_expansion_limit", "DOCX 正文大小超过上限。", status_code=413)
            with archive.open(entry) as stream:
                xml = stream.read(DOCX_MAX_DOCUMENT_BYTES + 1)
            if len(xml) > DOCX_MAX_DOCUMENT_BYTES:
                raise MaterialParseError("docx_expansion_limit", "DOCX 正文大小超过上限。", status_code=413)
            # Reject DTD/entity expansion before either XML parser sees the body.
            if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                raise MaterialParseError("invalid_docx", "DOCX 正文不支持 DTD 或实体。")
        root = ElementTree.fromstring(xml)
        try:
            from docx import Document
        except ImportError:
            return "\n".join(node.text for node in root.iter() if node.tag.endswith("}t") and node.text)
        doc = Document(io.BytesIO(data))
        return "\n\n".join(para.text.strip() for para in doc.paragraphs if para.text.strip())
    except MaterialParseError:
        raise
    except Exception as exc:
        raise MaterialParseError("invalid_docx", "DOCX 文件无法解析。") from exc


def parse_material_bytes(filename: str, data: bytes, *, text_cap: int = DEFAULT_TEXT_CAP, page_cap: int = 30) -> str:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in SUPPORTED_EXTENSIONS:
        raise MaterialParseError("unsupported_type", "仅支持 TXT、Markdown、PDF 和 DOCX 材料。", status_code=415)
    if suffix in {".txt", ".md", ".markdown"}:
        text = data.decode("utf-8", "replace")
        if suffix in {".md", ".markdown"}:
            text = _parse_markdown(text)
    elif suffix == ".pdf":
        text = _parse_pdf(data, page_cap, text_cap)
    else:
        text = _parse_docx(data)
    text = _clean_text(text)
    if not text:
        raise MaterialParseError("empty_text", "材料没有可用文本。")
    if len(text) > text_cap:
        raise MaterialParseError("text_limit", "材料文本超过上限，请拆分材料后上传。", status_code=413)
    return text
