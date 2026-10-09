"""Bounded material parsing; excessive inputs are rejected, never clipped."""
from __future__ import annotations

import base64
import io
import re
import zlib
from zipfile import ZipFile
from xml.etree import ElementTree

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx"}
DEFAULT_TEXT_CAP = 120_000
DOCX_MAX_ENTRIES = 256
DOCX_MAX_COMPRESSED_BYTES = 2 * 1024 * 1024
DOCX_MAX_TOTAL_BYTES = 16_000_000
DOCX_MAX_ENTRY_BYTES = 8_000_000
DOCX_MAX_DOCUMENT_BYTES = 2_000_000
PDF_MAX_STREAMS = 128
PDF_MAX_OBJECTS = 2_048
PDF_MAX_DECODED_STREAM_BYTES = 1_000_000
PDF_MAX_TOTAL_DECODED_BYTES = 4_000_000
PDF_MAX_EXPANSION_RATIO = 200
PDF_ROOT_OBJECT_RECOVERY_LIMIT = 1_024
_PDF_WHITESPACE = b"\x00\x09\x0a\x0c\x0d\x20"
_PDF_DELIMITERS = _PDF_WHITESPACE + b"()<>[]{}/%"


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


def _pdf_limit_error(message: str = "PDF 解码流超过安全上限，请拆分材料后上传。") -> MaterialParseError:
    return MaterialParseError("pdf_expansion_limit", message, status_code=413)


def _pdf_unsupported_stream(message: str) -> MaterialParseError:
    return MaterialParseError("pdf_stream_unsupported", message)


def _skip_pdf_space_and_comments(data: bytes, position: int, end: int) -> int:
    while position < end:
        if data[position] in _PDF_WHITESPACE:
            position += 1
            continue
        if data[position] == ord("%"):
            position += 1
            while position < end and data[position] not in b"\r\n":
                position += 1
            continue
        break
    return position


def _skip_pdf_literal(data: bytes, position: int, end: int) -> int:
    """Skip a PDF literal string without treating its contents as syntax."""
    depth = 1
    position += 1
    while position < end:
        char = data[position]
        if char == ord("\\"):
            position += 2
            continue
        if char == ord("("):
            depth += 1
        elif char == ord(")"):
            depth -= 1
            if depth == 0:
                return position + 1
        position += 1
    raise _pdf_unsupported_stream("PDF 字符串结构不完整。")


def _skip_pdf_hex(data: bytes, position: int, end: int) -> int:
    position += 1
    while position < end:
        if data[position] == ord(">"):
            return position + 1
        position += 1
    raise _pdf_unsupported_stream("PDF 十六进制字符串结构不完整。")


def _find_pdf_dictionary_end(data: bytes, position: int, end: int) -> int:
    """Return the byte just after a balanced dictionary, skipping strings/comments."""
    depth = 0
    while position < end:
        if (depth > 0 and data.startswith(b"stream", position)
                and position > 0 and data[position - 1] in _PDF_WHITESPACE
                and (position + 6 == end or data[position + 6] in _PDF_WHITESPACE)):
            raise _pdf_unsupported_stream("PDF 嵌套数据流暂不支持，请导出普通文字 PDF 或使用 TXT/Markdown。")
        if data.startswith(b"<<", position):
            depth += 1
            position += 2
            continue
        if data.startswith(b">>", position):
            depth -= 1
            position += 2
            if depth == 0:
                return position
            continue
        char = data[position]
        if char == ord("("):
            position = _skip_pdf_literal(data, position, end)
        elif char == ord("%"):
            position = _skip_pdf_space_and_comments(data, position, end)
        elif char == ord("<"):
            position = _skip_pdf_hex(data, position, end)
        else:
            position += 1
    raise _pdf_unsupported_stream("PDF 字典结构不完整。")


def _read_pdf_token(data: bytes, position: int, end: int) -> tuple[bytes, int]:
    position = _skip_pdf_space_and_comments(data, position, end)
    if position >= end:
        return b"", position
    if data.startswith(b"<<", position) or data.startswith(b">>", position):
        return data[position:position + 2], position + 2
    char = data[position]
    if char in b"[]":
        return data[position:position + 1], position + 1
    if char == ord("("):
        return b"(string)", _skip_pdf_literal(data, position, end)
    if char == ord("<"):
        return b"<hex>", _skip_pdf_hex(data, position, end)
    start = position
    if char == ord("/"):
        position += 1
    while position < end and data[position] not in _PDF_DELIMITERS:
        position += 1
    if position == start:
        raise _pdf_unsupported_stream("PDF 字典包含不支持的语法。")
    token = data[start:position]
    if token.startswith(b"/") and b"#" in token:
        # PDF names use #hh byte escapes for keys as well as filter names.
        if re.search(rb"#(?![0-9a-fA-F]{2})", token):
            raise _pdf_unsupported_stream("PDF 名称转义无效。")
        token = re.sub(rb"#([0-9a-fA-F]{2})", lambda match: bytes([int(match[1], 16)]), token)
    return token, position


def _pdf_dictionary_tokens(data: bytes, start: int, end: int) -> list[tuple[bytes, int]]:
    """Tokenize an already bounded dictionary; depth zero is its top level."""
    tokens: list[tuple[bytes, int]] = []
    depth = 0
    position = start + 2
    limit = end - 2
    while position < limit:
        token, position = _read_pdf_token(data, position, limit)
        if not token:
            break
        if token in {b"<<", b"["}:
            tokens.append((token, depth))
            depth += 1
        elif token in {b">>", b"]"}:
            depth -= 1
            if depth < 0:
                raise _pdf_unsupported_stream("PDF 字典嵌套无效。")
            tokens.append((token, depth))
        else:
            tokens.append((token, depth))
    if depth != 0:
        raise _pdf_unsupported_stream("PDF 字典嵌套无效。")
    return tokens


def _pdf_direct_length(tokens: list[tuple[bytes, int]]) -> int:
    for index, (token, depth) in enumerate(tokens):
        if depth != 0 or token != b"/Length":
            continue
        if index + 1 >= len(tokens) or tokens[index + 1][1] != 0:
            break
        value = tokens[index + 1][0]
        if not value.isdigit():
            raise _pdf_unsupported_stream("PDF 不支持间接或非整数的流长度。")
        if len(value) > 7:
            raise _pdf_limit_error("PDF 流长度超过安全上限。")
        if (index + 3 < len(tokens)
                and tokens[index + 2][1] == 0 and tokens[index + 2][0].isdigit()
                and tokens[index + 3] == (b"R", 0)):
            raise _pdf_unsupported_stream("PDF 不支持间接流长度。")
        return int(value)
    raise _pdf_unsupported_stream("PDF 流缺少直接长度。")


def _pdf_filters(tokens: list[tuple[bytes, int]]) -> list[bytes]:
    for index, (token, depth) in enumerate(tokens):
        if depth != 0 or token != b"/Filter":
            continue
        if index + 1 >= len(tokens) or tokens[index + 1][1] != 0:
            break
        value = tokens[index + 1][0]
        if value.startswith(b"/"):
            return [value]
        if value != b"[":
            raise _pdf_unsupported_stream("PDF 不支持间接或非标准过滤器。")
        filters: list[bytes] = []
        cursor = index + 2
        while cursor < len(tokens):
            candidate, candidate_depth = tokens[cursor]
            if candidate == b"]" and candidate_depth == 0:
                return filters
            if candidate_depth != 1 or not candidate.startswith(b"/"):
                raise _pdf_unsupported_stream("PDF 过滤器数组无效。")
            filters.append(candidate)
            cursor += 1
        raise _pdf_unsupported_stream("PDF 过滤器数组不完整。")
    return []


def _bounded_flate(data: bytes, limit: int) -> bytes:
    try:
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(data, limit + 1)
        if len(decoded) > limit or decoder.unconsumed_tail:
            raise _pdf_limit_error()
        tail = decoder.flush(limit + 1 - len(decoded))
        if len(decoded) + len(tail) > limit:
            raise _pdf_limit_error()
        if not decoder.eof:
            raise _pdf_unsupported_stream("PDF Flate 流不完整。")
        return decoded + tail
    except MaterialParseError:
        raise
    except Exception as exc:
        raise _pdf_unsupported_stream("PDF Flate 流无法安全解码。") from exc


def _bounded_ascii85(data: bytes, limit: int) -> bytes:
    payload = b"".join(data.split())
    if payload.endswith(b"~>"):
        payload = payload[:-2]
    if b"~>" in payload:
        raise _pdf_unsupported_stream("PDF ASCII85 流无效。")
    try:
        decoded = base64.a85decode(payload, adobe=False)
    except Exception as exc:
        raise _pdf_unsupported_stream("PDF ASCII85 流无法安全解码。") from exc
    if len(decoded) > limit:
        raise _pdf_limit_error()
    return decoded


def _bounded_asciihex(data: bytes, limit: int) -> bytes:
    payload = b"".join(data.split())
    if payload.endswith(b">"):
        payload = payload[:-1]
    if len(payload) % 2:
        payload += b"0"
    try:
        decoded = bytes.fromhex(payload.decode("ascii"))
    except Exception as exc:
        raise _pdf_unsupported_stream("PDF ASCIIHex 流无法安全解码。") from exc
    if len(decoded) > limit:
        raise _pdf_limit_error()
    return decoded


def _bounded_runlength(data: bytes, limit: int) -> bytes:
    decoded = bytearray()
    position = 0
    while position < len(data):
        control = data[position]
        position += 1
        if control == 128:
            return bytes(decoded)
        if control <= 127:
            count = control + 1
            if position + count > len(data):
                raise _pdf_unsupported_stream("PDF RunLength 流不完整。")
            if len(decoded) + count > limit:
                raise _pdf_limit_error()
            decoded.extend(data[position:position + count])
            position += count
            continue
        if position >= len(data):
            raise _pdf_unsupported_stream("PDF RunLength 流不完整。")
        if len(decoded) + 257 - control > limit:
            raise _pdf_limit_error()
        decoded.extend(data[position:position + 1] * (257 - control))
        position += 1
    raise _pdf_unsupported_stream("PDF RunLength 流缺少结束标记。")


def _decode_pdf_stream_bounded(raw: bytes, filters: list[bytes]) -> int:
    stream_limit = min(
        PDF_MAX_DECODED_STREAM_BYTES,
        max(1_024, len(raw) * PDF_MAX_EXPANSION_RATIO),
    )
    if len(raw) > stream_limit:
        raise _pdf_limit_error()
    decoded = raw
    work = 0
    for filter_name in filters:
        if filter_name in {b"/FlateDecode", b"/Fl"}:
            decoded = _bounded_flate(decoded, stream_limit)
        elif filter_name in {b"/ASCII85Decode", b"/A85"}:
            decoded = _bounded_ascii85(decoded, stream_limit)
        elif filter_name in {b"/ASCIIHexDecode", b"/AHx"}:
            decoded = _bounded_asciihex(decoded, stream_limit)
        elif filter_name in {b"/RunLengthDecode", b"/RL"}:
            decoded = _bounded_runlength(decoded, stream_limit)
        else:
            raise _pdf_unsupported_stream("PDF 使用不支持的压缩、图像或加密过滤器。")
        work += len(decoded)
        if work > PDF_MAX_TOTAL_DECODED_BYTES:
            raise _pdf_limit_error()
    return len(raw) if not filters else work


def _stream_data_start(data: bytes, position: int, end: int) -> int:
    """Require the PDF-specified line ending immediately after ``stream``."""
    if position >= end:
        raise _pdf_unsupported_stream("PDF 流缺少内容。")
    if data.startswith(b"\r\n", position):
        return position + 2
    if data[position] in b"\r\n":
        return position + 1
    raise _pdf_unsupported_stream("PDF 流缺少标准换行。")


def _pdf_object_header_end(data: bytes, position: int, end: int) -> int | None:
    """Recognize a direct object header outside skipped strings and streams."""
    if data[position] not in b"0123456789":
        return None
    first_end = position
    while first_end < end and data[first_end] in b"0123456789":
        first_end += 1
    second_start = _skip_pdf_space_and_comments(data, first_end, end)
    second_end = second_start
    while second_end < end and data[second_end] in b"0123456789":
        second_end += 1
    if second_end == second_start:
        return None
    keyword_start = _skip_pdf_space_and_comments(data, second_end, end)
    keyword_end = keyword_start + len(b"obj")
    if (data.startswith(b"obj", keyword_start)
            and (keyword_end >= end or data[keyword_end] in _PDF_DELIMITERS)):
        return keyword_end
    return None


def _preflight_pdf_streams(data: bytes) -> None:
    """Bound every direct PDF stream before pypdf can decode any of them.

    The scanner is syntax-aware for dictionaries, comments, literal strings and
    hex strings. It only accepts a direct ``/Length`` so stream bytes can be
    skipped without searching inside compressed data for an ``endstream`` token.
    Indirect lengths and filters without a small, bounded local decoder are
    deliberately rejected rather than delegated to pypdf's unrestricted decoder.
    """
    position = 0
    end = len(data)
    stream_count = 0
    object_count = 0
    total_work = 0
    while position < end:
        if data.startswith(b"<<", position):
            dictionary_start = position
            dictionary_end = _find_pdf_dictionary_end(data, position, end)
            next_position = _skip_pdf_space_and_comments(data, dictionary_end, end)
            if not data.startswith(b"stream", next_position):
                position = dictionary_end
                continue
            after_keyword = next_position + len(b"stream")
            if after_keyword < end and data[after_keyword] not in _PDF_DELIMITERS:
                position = dictionary_end
                continue
            stream_count += 1
            if stream_count > PDF_MAX_STREAMS:
                raise _pdf_limit_error("PDF 包含过多数据流，请拆分材料后上传。")
            tokens = _pdf_dictionary_tokens(data, dictionary_start, dictionary_end)
            # Hidden object/xref streams can introduce objects or resource
            # declarations not validated by this conservative direct-stream scan.
            for index, (token, depth) in enumerate(tokens):
                if depth == 0 and token == b"/Type" and index + 1 < len(tokens):
                    if tokens[index + 1][0] in {b"/ObjStm", b"/XRef"}:
                        raise _pdf_unsupported_stream("PDF 压缩对象或交叉引用流暂不支持，请导出普通文字 PDF 或使用 TXT/Markdown。")
                if depth == 0 and token == b"/Subtype" and index + 1 < len(tokens):
                    if tokens[index + 1][0] == b"/Form":
                        raise _pdf_unsupported_stream("PDF Form 引用暂不支持，请导出普通文字 PDF 或使用 TXT/Markdown。")
                if depth == 0 and token in {b"/DecodeParms", b"/DP", b"/F", b"/FFilter", b"/FDecodeParms"}:
                    raise _pdf_unsupported_stream("PDF 自定义解码参数或外部流暂不支持，请导出普通文字 PDF 或使用 TXT/Markdown。")
            length = _pdf_direct_length(tokens)
            stream_start = _stream_data_start(data, after_keyword, end)
            stream_end = stream_start + length
            if stream_end > end:
                raise _pdf_unsupported_stream("PDF 流长度无效。")
            marker = stream_end
            if data.startswith(b"\r\n", marker):
                marker += 2
            elif marker < end and data[marker] in b"\r\n":
                marker += 1
            if not data.startswith(b"endstream", marker):
                raise _pdf_unsupported_stream("PDF 流结束标记无效。")
            marker_end = marker + len(b"endstream")
            if marker_end < end and data[marker_end] not in _PDF_DELIMITERS:
                raise _pdf_unsupported_stream("PDF 流结束标记无效。")
            total_work += _decode_pdf_stream_bounded(data[stream_start:stream_end], _pdf_filters(tokens))
            if total_work > PDF_MAX_TOTAL_DECODED_BYTES:
                raise _pdf_limit_error("PDF 解码流总量超过安全上限，请拆分材料后上传。")
            position = marker_end
            continue
        object_end = _pdf_object_header_end(data, position, end)
        if object_end is not None:
            object_count += 1
            if object_count > PDF_MAX_OBJECTS:
                raise _pdf_limit_error("PDF 包含过多对象，请拆分材料后上传。")
            position = object_end
            continue
        char = data[position]
        if char == ord("("):
            position = _skip_pdf_literal(data, position, end)
        elif char == ord("%"):
            position = _skip_pdf_space_and_comments(data, position, end)
        elif char == ord("<"):
            position = _skip_pdf_hex(data, position, end)
        else:
            position += 1


def _parse_pdf(data: bytes, page_cap: int, text_cap: int) -> str:
    if not data.lstrip().startswith(b"%PDF"):
        raise MaterialParseError("invalid_pdf", "PDF 文件无法解析。")
    _preflight_pdf_streams(data)
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise MaterialParseError("pdf_dependency_missing", "PDF 解析依赖未安装，请安装 web 可选依赖 pypdf。", status_code=503) from exc
    try:
        reader = PdfReader(io.BytesIO(data), strict=False, root_object_recovery_limit=PDF_ROOT_OBJECT_RECOVERY_LIMIT)
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
