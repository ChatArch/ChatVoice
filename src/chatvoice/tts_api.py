"""Independent, CPU-only TTS configuration and bounded HTTP adapters."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import partial
import base64
import hashlib
import http.client
import io
import json
import math
import queue
import re
import socket
import threading
import time
from typing import Any
from urllib.parse import urlsplit
import urllib.error
import urllib.request
import wave


FIELDS = ('API_TYPE', 'API_BASE', 'API_KEY', 'MODEL', 'RESOURCE_ID', 'VOICES')
MAX_RESPONSE_BYTES = 24 * 1024 * 1024
MAX_LINE_BYTES = 2 * 1024 * 1024
MAX_AUDIO_BYTES = 16 * 1024 * 1024
TOTAL_SECONDS = 60
IO_SECONDS = 10
CONFIG_ERROR = '语音合成配置不完整或无效，请检查独立 TTS 配置。'
REQUEST_ERROR = '语音合成服务请求失败，请稍后重试。'
_DNS_SLOTS = threading.BoundedSemaphore(4)


class TTSConfigurationError(ValueError):
    """Safe configuration failure (HTTP 503)."""


class TTSRequestError(RuntimeError):
    """Safe upstream failure (HTTP 502)."""


@dataclass(frozen=True)
class TTSSettings:
    provider: str
    base: str
    key: str = field(repr=False)
    model: str
    resource_id: str = field(repr=False)
    voices: tuple[tuple[str, str], ...]


def _header(value: Any, maximum: int = 256) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= maximum and value == value.strip()
            and all(32 <= ord(char) < 127 for char in value))


def _host(base: str, *, websocket: bool = False) -> str | None:
    try:
        parsed = urlsplit(base)
        if (not base.isascii() or any(ord(char) <= 32 or ord(char) == 127 for char in base)
                or '\\' in base or '?' in base or '#' in base
                or parsed.scheme not in ({'ws', 'wss'} if websocket else {'http', 'https'}) or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or not re.fullmatch(r'[A-Za-z0-9.:-]+', parsed.hostname)):
            return None
        parsed.port
        return parsed.hostname
    except (ValueError, TypeError):
        return None


def resolve_tts_settings(values: Mapping[str, Any]) -> TTSSettings | None:
    """Any nonempty independent field opts in; never borrow other credentials."""
    raw = [values.get(f'CHATVOICE_TTS_{name}') or '' for name in FIELDS]
    if not any(raw):
        return None
    try:
        if not all(isinstance(value, str) for value in raw):
            raise ValueError
        provider, base, key, model, resource, voices_json = raw
        if (provider not in {'volcengine', 'openai', 'qwen'} or not _host(base, websocket=provider == 'qwen')
                or not _header(key, 4096) or not _header(model)
                or (provider == 'qwen' and not key.startswith('sk-sp'))
                or (provider == 'volcengine' and not _header(resource))
                or (resource and not _header(resource)) or len(voices_json) > 32768):
            raise ValueError
        voices = json.loads(voices_json)
        if not isinstance(voices, list) or not 1 <= len(voices) <= 64:
            raise ValueError
        voice_ids, labels = set(), set()
        result = []
        for voice in voices:
            if not isinstance(voice, dict) or set(voice) != {'id', 'label'}:
                raise ValueError
            voice_id, label = voice['id'], voice['label']
            if (not _header(voice_id, 80) or voice_id == 'clone' or not voice_id.strip()
                    or not isinstance(label, str) or not 1 <= len(label) <= 80 or not label.strip()
                    or any(ord(char) < 32 or 127 <= ord(char) <= 159 or char in '<>' for char in label)
                    or voice_id in voice_ids or label in labels):
                raise ValueError
            voice_ids.add(voice_id)
            labels.add(label)
            result.append((voice_id, label))
        return TTSSettings(provider, base if provider == 'qwen' else base.rstrip('/'), key, model, resource, tuple(result))
    except Exception:
        raise TTSConfigurationError(CONFIG_ERROR) from None


def tts_status(values: Mapping[str, Any]) -> dict[str, Any] | None:
    try:
        settings = resolve_tts_settings(values)
    except TTSConfigurationError:
        return {'provider': None, 'base_host': None, 'model': None,
                'key_configured': bool(values.get('CHATVOICE_TTS_API_KEY')),
                'configured': False, 'voices': [], 'default_voice': None, 'error': CONFIG_ERROR}
    if settings is None:
        return None
    return {'provider': settings.provider, 'base_host': _host(settings.base, websocket=settings.provider == 'qwen'), 'model': settings.model,
            'key_configured': bool(settings.key), 'configured': True,
            'voices': [{'id': voice_id, 'label': label} for voice_id, label in settings.voices],
            'default_voice': settings.voices[0][0]}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _DeadlineReader:
    def __init__(self, reader, connection, deadline: float):
        self.reader = reader
        self.connection = connection
        self.deadline = deadline

    def __getattr__(self, name):
        return getattr(self.reader, name)

    def read1(self, size=-1):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        self.connection.settimeout(min(IO_SECONDS, remaining))
        result = self.reader.read1(size)
        if time.monotonic() >= self.deadline:
            raise TimeoutError
        return result

    def read(self, size=-1):
        result = bytearray()
        while size < 0 or len(result) < size:
            chunk = self.read1(65536 if size < 0 else size - len(result))
            if not chunk:
                break
            result.extend(chunk)
        return bytes(result)

    def readline(self, size=-1):
        result = bytearray()
        while size < 0 or len(result) < size:
            chunk = self.read1(1)
            if not chunk:
                break
            result.extend(chunk)
            if chunk == b'\n':
                break
        return bytes(result)


class _DeadlineResponse(http.client.HTTPResponse):
    def __init__(self, connection, *args, deadline, **kwargs):
        super().__init__(connection, *args, **kwargs)
        self.fp = _DeadlineReader(self.fp, connection, deadline)


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    return remaining


def _resolve_addresses(host, port, deadline: float):
    if not _DNS_SLOTS.acquire(timeout=_remaining(deadline)):
        raise TimeoutError
    results = queue.Queue(maxsize=1)

    def resolve():
        try:
            results.put((socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM), None))
        except Exception as error:
            results.put((None, error))
        finally:
            _DNS_SLOTS.release()

    try:
        threading.Thread(target=resolve, daemon=True, name='tts-dns').start()
    except Exception:
        _DNS_SLOTS.release()
        raise
    try:
        addresses, error = results.get(timeout=_remaining(deadline))
    except queue.Empty:
        raise TimeoutError from None
    if error is not None:
        raise error
    return addresses


def _connect(address, timeout, source_address=None, *, deadline):
    for family, kind, protocol, _, destination in _resolve_addresses(*address, deadline):
        connection = socket.socket(family, kind, protocol)
        try:
            connection.settimeout(min(timeout, _remaining(deadline)))
            if source_address:
                connection.bind(source_address)
            connection.connect(destination)
            connection.settimeout(min(timeout, _remaining(deadline)))
            return connection
        except Exception:
            connection.close()
    raise OSError('TTS connection failed')


def _open_request(request: urllib.request.Request, timeout: float):
    deadline = request.tts_deadline

    def connection(connection_type, host, **kwargs):
        result = connection_type(host, **kwargs)
        result._create_connection = partial(_connect, deadline=deadline)
        result.response_class = partial(_DeadlineResponse, deadline=deadline)
        return result

    class HTTPHandler(urllib.request.HTTPHandler):
        def http_open(self, req):
            return self.do_open(partial(connection, http.client.HTTPConnection), req)

    class HTTPSHandler(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(partial(connection, http.client.HTTPSConnection), req, context=self._context)

    return urllib.request.build_opener(_NoRedirect(), HTTPHandler(), HTTPSHandler()).open(request, timeout=timeout)


def _chunks(response, deadline: float):
    total = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TTSRequestError(REQUEST_ERROR)
        connection = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
        if connection is not None:
            connection.settimeout(min(IO_SECONDS, remaining))
        chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - total))
        if time.monotonic() >= deadline:
            raise TTSRequestError(REQUEST_ERROR)
        if not chunk:
            if getattr(response, 'length', None) not in (None, 0):
                raise TTSRequestError(REQUEST_ERROR)
            return
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise TTSRequestError(REQUEST_ERROR)
        yield chunk


def _events(response, deadline: float):
    pending = bytearray()
    for chunk in _chunks(response, deadline):
        pending.extend(chunk)
        while b'\n' in pending:
            line, _, remainder = pending.partition(b'\n')
            pending = bytearray(remainder)
            if len(line) > MAX_LINE_BYTES:
                raise TTSRequestError(REQUEST_ERROR)
            if line.strip():
                yield json.loads(line)
        if len(pending) > MAX_LINE_BYTES:
            raise TTSRequestError(REQUEST_ERROR)
    if pending.strip():
        yield json.loads(pending)


def _valid_audio(audio: bytes, format: str) -> bool:
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        return False
    if format == 'pcm':
        return len(audio) % 2 == 0
    if format == 'wav':
        try:
            if audio[:4] != b'RIFF' or audio[8:12] != b'WAVE' or int.from_bytes(audio[4:8], 'little') + 8 != len(audio):
                return False
            with wave.open(io.BytesIO(audio), 'rb') as source:
                expected = source.getnframes() * source.getnchannels() * source.getsampwidth()
                return (source.getcomptype() == 'NONE' and source.getframerate() > 0
                        and 0 < expected <= MAX_AUDIO_BYTES and len(source.readframes(source.getnframes())) == expected)
        except (wave.Error, EOFError):
            return False
    offset = 0
    if audio.startswith(b'ID3'):
        if len(audio) < 10 or any(value >= 128 for value in audio[6:10]):
            return False
        offset = 10 + sum(value << shift for value, shift in zip(audio[6:10], (21, 14, 7, 0)))
        if audio[5] & 16:
            offset += 10
    if len(audio) < offset + 4:
        return False
    header = int.from_bytes(audio[offset:offset + 4], 'big')
    version, layer = (header >> 19) & 3, (header >> 17) & 3
    bitrate_index, sample_index = (header >> 12) & 15, (header >> 10) & 3
    if header >> 21 != 2047 or version == 1 or layer != 1 or bitrate_index in {0, 15} or sample_index == 3:
        return False
    bitrates = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320) if version == 3 else (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
    sample_rate = (44100, 48000, 32000)[sample_index] // (1 if version == 3 else 2 if version == 2 else 4)
    frame_size = (144 if version == 3 else 72) * bitrates[bitrate_index] * 1000 // sample_rate + ((header >> 9) & 1)
    return len(audio) >= offset + frame_size


def synthesize(settings: TTSSettings, text: str, *, voice: str | None = None, format: str = 'mp3') -> dict[str, Any]:
    selected = settings.voices[0][0] if voice is None else voice
    if selected not in {voice_id for voice_id, _ in settings.voices} or format not in {'mp3', 'wav'}:
        raise TTSConfigurationError(CONFIG_ERROR)
    if settings.provider == 'qwen':
        from chatvoice.tts_qwen import synthesize_qwen
        return synthesize_qwen(settings, text, selected, format)
    started = time.monotonic()
    deadline = started + TOTAL_SECONDS
    wire_format = 'pcm' if settings.provider == 'volcengine' and format == 'wav' else format
    headers = {'Content-Type': 'application/json'}
    if settings.provider == 'volcengine':
        operation = '/tts/unidirectional'
        headers.update({'X-Api-Key': settings.key, 'X-Api-Resource-Id': settings.resource_id})
        payload = {'req_params': {'text': text, 'speaker': selected,
                                  'audio_params': {'format': wire_format, 'sample_rate': 24000}}}
    else:
        operation = '/audio/speech'
        headers['Authorization'] = f'Bearer {settings.key}'
        payload = {'model': settings.model, 'input': text, 'voice': selected, 'response_format': format}
    try:
        request = urllib.request.Request(settings.base + operation, data=json.dumps(payload).encode(), headers=headers, method='POST')
        request.tts_deadline = deadline
        audio = bytearray()
        usage = {}
        with _open_request(request, timeout=min(IO_SECONDS, TOTAL_SECONDS)) as response:
            if response.status != 200:
                raise TTSRequestError(REQUEST_ERROR)
            if settings.provider == 'volcengine':
                terminal = False
                for event in _events(response, deadline):
                    if not isinstance(event, dict) or terminal or type(event.get('code')) is not int:
                        raise TTSRequestError(REQUEST_ERROR)
                    code = event['code']
                    if code == 20000000:
                        terminal = True
                        if event.get('data') not in (None, ''):
                            raise TTSRequestError(REQUEST_ERROR)
                        if isinstance(event.get('usage'), dict):
                            usage = {name: value for name, value in event['usage'].items()
                                     if name in {'text_words', 'input_tokens', 'output_tokens', 'total_tokens'}
                                     and type(value) in {int, float} and math.isfinite(value) and 0 <= value <= 10**12}
                    elif code == 0:
                        encoded = event.get('data')
                        if 'data' in event and encoded is None and isinstance(event.get('sentence'), dict):
                            continue
                        if not isinstance(encoded, str):
                            raise TTSRequestError(REQUEST_ERROR)
                        audio.extend(base64.b64decode(encoded, validate=True))
                        if len(audio) > MAX_AUDIO_BYTES:
                            raise TTSRequestError(REQUEST_ERROR)
                    else:
                        raise TTSRequestError(REQUEST_ERROR)
                if not terminal:
                    raise TTSRequestError(REQUEST_ERROR)
            else:
                for chunk in _chunks(response, deadline):
                    audio.extend(chunk)
                    if len(audio) > MAX_AUDIO_BYTES:
                        raise TTSRequestError(REQUEST_ERROR)
        if not _valid_audio(bytes(audio), wire_format):
            raise TTSRequestError(REQUEST_ERROR)
        if wire_format == 'pcm':
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as output:
                output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                output.writeframes(audio)
            audio = buffer.getvalue()
            if not _valid_audio(audio, 'wav'):
                raise TTSRequestError(REQUEST_ERROR)
        return {'audio': bytes(audio), 'provider': settings.provider, 'model': settings.model, 'voice': selected,
                'elapsed_ms': round((time.monotonic() - started) * 1000), 'usage': usage,
                'request_id': None, 'sha256_12': hashlib.sha256(audio).hexdigest()[:12]}
    except urllib.error.HTTPError as error:
        error.close()
        raise TTSRequestError(REQUEST_ERROR) from None
    except Exception:
        raise TTSRequestError(REQUEST_ERROR) from None


def probe_tts_configuration(values: Mapping[str, Any]) -> dict[str, Any] | None:
    settings = resolve_tts_settings(values)
    if settings is None:
        return None
    result = synthesize(settings, '你好，这是一段合成测试。')
    return {name: result[name] for name in ('provider', 'model', 'voice', 'elapsed_ms')}
