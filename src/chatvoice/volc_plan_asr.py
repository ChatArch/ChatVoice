"""Bounded native Volcengine Agent Plan streaming ASR transport."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import gzip
import json
import struct
import uuid
import zlib

import aiohttp

from chatvoice.asr_routing import PlanSettings


MAX_UPSTREAM_FRAME = 64 * 1024
MAX_DECODED_JSON = 32 * 1024
MAX_AUDIO_PACKET = 24 * 1024


class PlanError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Plan ASR {reason}")


@dataclass(frozen=True)
class PlanResponse:
    sequence: int
    terminal: bool
    text: str
    code: int
    valid_terminal: bool
    error_reason: str | None = None


def _frame(message_type: int, flags: int, sequence: int, payload: bytes, *, serialization: int = 1) -> bytes:
    if len(payload) > MAX_UPSTREAM_FRAME - 12:
        raise ValueError("ASR frame too large")
    return bytes((0x11, message_type << 4 | flags, serialization << 4 | 1, 0)) + struct.pack(">iI", sequence, len(payload)) + payload


def encode_request(sequence: int, model: str, rate: int = 16000) -> bytes:
    if model != "bigmodel" or rate not in {8000, 16000, 24000, 48000}:
        raise ValueError("unsupported Plan ASR request")
    body = {
        "user": {"uid": "chatvoice"},
        "audio": {"format": "pcm", "codec": "raw", "rate": rate, "bits": 16, "channel": 1},
        "request": {"model_name": model, "enable_itn": True, "enable_punc": True,
                    "enable_ddc": True, "show_utterances": True, "enable_nonstream": False},
    }
    return _frame(1, 1, sequence, gzip.compress(json.dumps(body, separators=(",", ":")).encode()))


def encode_audio(sequence: int, pcm: bytes, *, last: bool) -> bytes:
    if len(pcm) > MAX_AUDIO_PACKET or len(pcm) % 2 or sequence <= 0:
        raise ValueError("invalid Plan audio packet")
    return _frame(2, 3 if last else 1, -sequence if last else sequence, gzip.compress(pcm), serialization=0)


def _bounded_gzip(data: bytes) -> bytes:
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        output = decompressor.decompress(data, MAX_DECODED_JSON + 1)
    except zlib.error:
        raise ValueError("invalid ASR gzip payload") from None
    if len(output) > MAX_DECODED_JSON or decompressor.unconsumed_tail or not decompressor.eof:
        raise ValueError("ASR JSON too large or incomplete")
    try:
        output += decompressor.flush(MAX_DECODED_JSON + 1 - len(output))
    except zlib.error:
        raise ValueError("invalid ASR gzip payload") from None
    if len(output) > MAX_DECODED_JSON:
        raise ValueError("ASR JSON too large")
    return output


def parse_response(frame: bytes) -> PlanResponse:
    if not isinstance(frame, bytes) or len(frame) < 8 or len(frame) > MAX_UPSTREAM_FRAME:
        raise ValueError("invalid ASR response frame")
    header_len = (frame[0] & 15) * 4
    if frame[0] >> 4 != 1 or header_len < 4 or header_len > 16 or len(frame) < header_len + 4:
        raise ValueError("invalid ASR response header")
    message_type, flags, serialization, compression = frame[1] >> 4, frame[1] & 15, frame[2] >> 4, frame[2] & 15
    if message_type not in {9, 15} or serialization != 1 or compression not in {0, 1}:
        raise ValueError("unsupported ASR response")
    offset = header_len
    sequence = 0
    if flags & 1:
        if len(frame) < offset + 4:
            raise ValueError("missing ASR sequence")
        sequence = struct.unpack_from(">i", frame, offset)[0]
        offset += 4
    if flags & 4:
        if len(frame) < offset + 4:
            raise ValueError("missing ASR event")
        offset += 4
    code = 0
    if message_type == 15:
        if len(frame) < offset + 4:
            raise ValueError("missing ASR error code")
        code = struct.unpack_from(">i", frame, offset)[0]
        offset += 4
    if len(frame) < offset + 4:
        raise ValueError("missing ASR payload size")
    size = struct.unpack_from(">I", frame, offset)[0]
    offset += 4
    if size != len(frame) - offset:
        raise ValueError("invalid ASR payload size")
    raw = _bounded_gzip(frame[offset:]) if compression == 1 else frame[offset:]
    if len(raw) > MAX_DECODED_JSON:
        raise ValueError("ASR JSON too large")
    try:
        body = json.loads(raw) if raw else {}
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid ASR JSON") from exc
    if not isinstance(body, dict):
        raise ValueError("invalid ASR response body")
    if isinstance(body.get("code"), int) and body["code"] != 0:
        code = body["code"]
    result = body.get("result")
    text = result.get("text", "") if isinstance(result, dict) else ""
    if not isinstance(text, str) or len(text) > MAX_DECODED_JSON:
        raise ValueError("invalid ASR text")
    terminal = bool(flags & 2)
    description = body.get("message") or body.get("msg") or ""
    success = message_type == 9 and code in {0, 20000000}
    reason = None if success else classify_failure(code, description=str(description)[:512])
    return PlanResponse(sequence, terminal, text, code, terminal and success and isinstance(result, dict), reason)


def classify_failure(code: int = 0, status: int = 0, description: str = "") -> str:
    lowered = description.lower()
    if any(word in lowered for word in ("quota", "exhaust", "余额", "额度")):
        return "quota"
    if any(word in lowered for word in ("expired", "subscription", "purchase", "套餐", "订阅", "未购买")):
        return "entitlement"
    if any(word in lowered for word in ("authentication", "permission", "api key", "鉴权", "权限")):
        return "authentication"
    if status in {401, 403} or code in {401, 403}:
        return "authentication"
    if status in {402, 429} or code in {402, 429}:
        return "quota"
    if code in {450000, 450001, 450002}:
        return "entitlement"
    return "protocol"


async def _refuse_redirect(_session: aiohttp.ClientSession, _context: object, _params: object) -> None:
    # aiohttp sends this trace before it follows a redirect with request headers.
    raise PlanError("redirect")


class PlanStream:
    """One upstream connection per commit window; no audio is replayed."""

    def __init__(self, settings: PlanSettings, *, sample_rate: int = 16000) -> None:
        if not settings.configured:
            raise PlanError("configuration")
        self.settings = settings
        self.sample_rate = sample_rate
        self.session: aiohttp.ClientSession | None = None
        self.ws: aiohttp.ClientWebSocketResponse | None = None
        self.sequence = 1
        self.pending = b""
        self.request_id = str(uuid.uuid4())

    async def start(self) -> PlanResponse:
        try:
            trace = aiohttp.TraceConfig()
            trace.on_request_redirect.append(_refuse_redirect)
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8), trust_env=False,
                                                 trace_configs=[trace])
            self.ws = await asyncio.wait_for(self.session.ws_connect(
                self.settings.base,
                headers={"X-Api-Key": self.settings.key, "X-Api-Resource-Id": self.settings.resource_id,
                         "X-Api-Request-Id": self.request_id, "X-Api-Connect-Id": self.request_id,
                         "X-Api-Sequence": "-1"},
                max_msg_size=MAX_UPSTREAM_FRAME, heartbeat=10,
            ), 5)
            await self.ws.send_bytes(encode_request(self.sequence, self.settings.model, self.sample_rate))
            self.sequence += 1
            response = await self.receive(timeout=5)
            if response.error_reason:
                raise PlanError(response.error_reason)
            return response
        except aiohttp.WSServerHandshakeError as exc:
            await self.close()
            raise PlanError(classify_failure(status=exc.status)) from None
        except (asyncio.TimeoutError, aiohttp.ClientError):
            await self.close()
            raise PlanError("network") from None
        except BaseException:
            await self.close()
            raise

    async def send_pcm(self, pcm: bytes) -> None:
        if not self.ws or len(pcm) % 2:
            raise PlanError("protocol")
        for offset in range(0, len(pcm), MAX_AUDIO_PACKET):
            piece = pcm[offset:offset + MAX_AUDIO_PACKET]
            if self.pending:
                await self._send(encode_audio(self.sequence, self.pending, last=False))
                self.sequence += 1
            self.pending = piece

    async def finish(self) -> None:
        if not self.ws:
            raise PlanError("protocol")
        await self._send(encode_audio(self.sequence, self.pending, last=True))
        self.pending = b""
        self.sequence += 1

    async def _send(self, frame: bytes) -> None:
        try:
            await asyncio.wait_for(self.ws.send_bytes(frame), 5)
        except asyncio.TimeoutError:
            raise PlanError("timeout") from None
        except (aiohttp.ClientError, OSError):
            raise PlanError("network") from None

    async def receive(self, *, timeout: float = 10) -> PlanResponse:
        if not self.ws:
            raise PlanError("protocol")
        try:
            message = await asyncio.wait_for(self.ws.receive(), timeout)
            if message.type != aiohttp.WSMsgType.BINARY:
                raise PlanError("protocol")
            response = parse_response(message.data)
            if response.sequence and abs(response.sequence) >= self.sequence:
                raise PlanError("protocol")
            if response.error_reason:
                raise PlanError(response.error_reason)
            return response
        except asyncio.TimeoutError:
            raise PlanError("timeout") from None
        except ValueError:
            raise PlanError("protocol") from None
        except (aiohttp.ClientError, OSError):
            raise PlanError("network") from None

    async def close(self) -> None:
        if self.ws:
            try:
                await asyncio.wait_for(self.ws.close(), 2)
            except (asyncio.TimeoutError, aiohttp.ClientError, OSError):
                pass
            self.ws = None
        if self.session:
            await self.session.close()
            self.session = None
