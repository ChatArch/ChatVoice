"""Per-call Qwen WebSocket TTS, without DashScope SDK globals."""

import hashlib
from contextlib import suppress
import json
import ssl
import time
from urllib.parse import urlsplit
import uuid

import websocket
from websocket._abnf import frame_buffer

from chatvoice import tts_api as api


class _DeadlineSocket:
    def __init__(self, connection, deadline):
        self.connection = connection
        self.deadline = deadline
        self.received = 0

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def recv(self, size):
        self.connection.settimeout(min(api.IO_SECONDS, api._remaining(self.deadline)))
        remaining = api.MAX_RESPONSE_BYTES - self.received
        data = self.connection.recv(min(size, remaining + 1, 65536))
        self.received += len(data)
        if self.received > api.MAX_RESPONSE_BYTES:
            raise api.TTSRequestError(api.REQUEST_ERROR)
        api._remaining(self.deadline)
        return data

    def send(self, data):
        self.connection.settimeout(min(api.IO_SECONDS, api._remaining(self.deadline)))
        result = self.connection.send(data)
        api._remaining(self.deadline)
        return result


def _transport(settings, deadline):
    parsed = urlsplit(settings.base)
    connection = api._connect((parsed.hostname, parsed.port or (443 if parsed.scheme == 'wss' else 80)),
                              api.IO_SECONDS, deadline=deadline)
    try:
        if parsed.scheme == 'wss':
            connection = ssl.create_default_context().wrap_socket(connection, server_hostname=parsed.hostname)
        api._remaining(deadline)
        return _DeadlineSocket(connection, deadline)
    except Exception:
        connection.close()
        raise


class _BoundedFrames(frame_buffer):
    def recv_length(self):
        super().recv_length()
        if self.length > api.MAX_LINE_BYTES:
            raise api.TTSRequestError(api.REQUEST_ERROR)


class _WebSocket(websocket.WebSocket):
    def __init__(self):
        super().__init__()
        self.frame_buffer = _BoundedFrames(self._recv, False)


def _open_socket(settings, deadline):
    if websocket.isEnabledForTrace():
        raise api.TTSRequestError(api.REQUEST_ERROR)
    connection = _WebSocket()
    transport = None
    try:
        transport = _transport(settings, deadline)
        connection.connect(settings.base, socket=transport, redirect_limit=0,
                           timeout=min(api.IO_SECONDS, api._remaining(deadline)),
                           header={'Authorization': f'Bearer {settings.key}'}, suppress_origin=True)
        if connection.handshake_response.status != 101:
            raise api.TTSRequestError(api.REQUEST_ERROR)
        return connection
    except Exception:
        connection.shutdown()
        if transport is not None:
            transport.close()
        raise


def _messages(connection, deadline):
    pending = bytearray()
    opcode = None
    while True:
        api._remaining(deadline)
        frame = connection.recv_frame()
        api._remaining(deadline)
        if frame.mask:
            raise api.TTSRequestError(api.REQUEST_ERROR)
        if frame.opcode == websocket.ABNF.OPCODE_PING:
            connection.pong(frame.data)
            continue
        if frame.opcode == websocket.ABNF.OPCODE_PONG:
            continue
        if frame.opcode == websocket.ABNF.OPCODE_CLOSE:
            raise api.TTSRequestError(api.REQUEST_ERROR)
        if frame.opcode in (websocket.ABNF.OPCODE_TEXT, websocket.ABNF.OPCODE_BINARY):
            if opcode is not None:
                raise api.TTSRequestError(api.REQUEST_ERROR)
            opcode = frame.opcode
        elif frame.opcode != websocket.ABNF.OPCODE_CONT or opcode is None:
            raise api.TTSRequestError(api.REQUEST_ERROR)
        pending.extend(frame.data)
        if len(pending) > (api.MAX_LINE_BYTES if opcode == websocket.ABNF.OPCODE_TEXT else api.MAX_AUDIO_BYTES):
            raise api.TTSRequestError(api.REQUEST_ERROR)
        if frame.fin:
            yield opcode, bytes(pending)
            pending.clear()
            opcode = None


def synthesize_qwen(settings, text, voice, format):
    started = time.monotonic()
    deadline = started + api.TOTAL_SECONDS
    connection = None
    task_id = uuid.uuid4().hex
    payload = {'model': settings.model, 'task_group': 'audio', 'task': 'tts', 'function': 'SpeechSynthesizer'}

    def send(action, body):
        api._remaining(deadline)
        connection.send(json.dumps({'header': {'action': action, 'task_id': task_id, 'streaming': 'duplex'},
                                    'payload': body}))

    try:
        connection = _open_socket(settings, deadline)
        send('run-task', {**payload, 'input': {}, 'parameters': {
            'voice': voice, 'volume': 50, 'text_type': 'PlainText', 'sample_rate': 24000,
            'rate': 1.0, 'format': format, 'pitch': 1.0, 'seed': 0, 'type': 0}})
        task_started = False
        audio = bytearray()
        for opcode, data in _messages(connection, deadline):
            if opcode == websocket.ABNF.OPCODE_BINARY:
                if not task_started:
                    raise api.TTSRequestError(api.REQUEST_ERROR)
                audio.extend(data)
                if len(audio) > api.MAX_AUDIO_BYTES:
                    raise api.TTSRequestError(api.REQUEST_ERROR)
                continue
            event = json.loads(data)
            header = event['header']
            if header.get('task_id') != task_id:
                raise api.TTSRequestError(api.REQUEST_ERROR)
            kind = header.get('event')
            if kind == 'task-started' and not task_started:
                task_started = True
                send('continue-task', {**payload, 'input': {'text': text}})
                send('finish-task', {'input': {}})
            elif kind == 'task-finished' and task_started:
                if not api._valid_audio(bytes(audio), format):
                    raise api.TTSRequestError(api.REQUEST_ERROR)
                return {'audio': bytes(audio), 'provider': 'qwen', 'model': settings.model, 'voice': voice,
                        'elapsed_ms': round((time.monotonic() - started) * 1000), 'usage': {},
                        'request_id': task_id, 'sha256_12': hashlib.sha256(audio).hexdigest()[:12]}
            elif kind != 'result-generated' or not task_started:
                raise api.TTSRequestError(api.REQUEST_ERROR)
    except Exception:
        raise api.TTSRequestError(api.REQUEST_ERROR) from None
    finally:
        if connection is not None:
            with suppress(Exception):
                connection.shutdown()
