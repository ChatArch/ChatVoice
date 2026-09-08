import importlib
import io
import json
import struct
import sys
import types
import wave

import pytest

from chatvoice import tts_api


MP3 = b'\xff\xfb\x90\x00' + bytes(413)


def config(**overrides):
    fields = {'API_TYPE': 'qwen', 'API_BASE': 'wss://speech.example.test/custom/',
              'API_KEY': 'sk-sp-independent-secret', 'MODEL': 'configured-qwen-model',
              'VOICES': '[{"id":"configured-voice","label":"Configured"}]'}
    return {f'CHATVOICE_TTS_{key}': value for key, value in {**fields, **overrides}.items()}


def helper():
    return importlib.import_module('chatvoice.tts_qwen')


def test_explicit_config_and_safe_status():
    settings = tts_api.resolve_tts_settings(config())
    assert settings.base == 'wss://speech.example.test/custom/'
    assert settings.resource_id == ''
    assert 'secret' not in repr(settings)
    status = tts_api.tts_status(config())
    assert status['provider'] == 'qwen' and status['configured']
    assert status['base_host'] == 'speech.example.test'
    assert 'secret' not in json.dumps(status)
    assert tts_api.resolve_tts_settings(config(API_BASE='ws://localhost:8080/tts')).provider == 'qwen'


@pytest.mark.parametrize('overrides', [
    {'API_KEY': 'sk-ordinary-secret'}, {'API_KEY': ''}, {'MODEL': ''}, {'VOICES': ''},
    {'API_BASE': 'https://speech.example.test'}, {'API_BASE': 'wss://user:secret@host/'},
    {'API_BASE': 'wss://host/?secret=1'}, {'API_BASE': 'wss://host/#secret'},
    {'API_BASE': 'wss://host/\r\nsecret'},
])
def test_config_rejects_without_borrowing(overrides):
    values = {**config(**overrides), 'CHATVOICE_OPENAI_API_KEY': 'sk-sp-unrelated-secret'}
    with pytest.raises(tts_api.TTSConfigurationError):
        tts_api.resolve_tts_settings(values)
    assert not tts_api.tts_status(values)['configured']


class FakeSocket:
    def __init__(self, events, status=101):
        self.events = iter(events)
        self.status = status
        self.sent = []
        self.closed = False

    def send(self, data):
        self.sent.append(json.loads(data))

    def recv_frame(self):
        event = next(self.events)
        if isinstance(event, Exception):
            raise event
        if isinstance(event, dict):
            event = {'header': {'task_id': self.sent[0]['header']['task_id'], **event}}
            return types.SimpleNamespace(opcode=1, fin=1, data=json.dumps(event).encode(), mask=0)
        return types.SimpleNamespace(opcode=2, fin=1, data=event, mask=0)

    def shutdown(self):
        self.closed = True


def install(monkeypatch, events):
    module = helper()
    connection = FakeSocket(events)
    calls = []
    def open_socket(settings, deadline):
        calls.append(settings)
        return connection
    monkeypatch.setattr(module, '_open_socket', open_socket)
    return module, connection, calls


@pytest.mark.parametrize('format', ['mp3', 'wav'])
def test_independent_dispatch_schemas_and_cleanup(monkeypatch, format):
    audio = MP3
    if format == 'wav':
        output = io.BytesIO()
        with wave.open(output, 'wb') as writer:
            writer.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            writer.writeframes(bytes(480))
        audio = output.getvalue()
    _, connection, calls = install(monkeypatch, [{'event': 'task-started'}, audio, {'event': 'task-finished'}])
    sentinel = types.SimpleNamespace(api_key='unrelated-global', base_websocket_api_url='unrelated-url')
    monkeypatch.setitem(sys.modules, 'dashscope', sentinel)
    result = tts_api.synthesize(tts_api.resolve_tts_settings(config()), 'synthetic', format=format)
    assert result['audio'] == audio
    assert result['provider'] == 'qwen' and result['model'] == 'configured-qwen-model'
    assert result['voice'] == 'configured-voice' and result['request_id']
    assert len(calls) == 1 and connection.closed
    assert sentinel.api_key == 'unrelated-global' and sentinel.base_websocket_api_url == 'unrelated-url'
    start, continuation, finish = connection.sent
    assert [command['header']['action'] for command in connection.sent] == ['run-task', 'continue-task', 'finish-task']
    assert all(command['header']['streaming'] == 'duplex' for command in connection.sent)
    assert len({command['header']['task_id'] for command in connection.sent}) == 1
    assert start['payload']['model'] == 'configured-qwen-model'
    assert start['payload']['parameters']['voice'] == 'configured-voice'
    assert start['payload']['parameters']['format'] == format
    assert start['payload']['parameters']['sample_rate'] == 24000
    assert start['payload']['input'] == {}
    assert continuation['payload']['input'] == {'text': 'synthetic'}
    assert finish['payload'] == {'input': {}}


@pytest.mark.parametrize('events', [
    [{'event': 'task-started'}, {'event': 'task-finished'}],
    [{'event': 'task-started'}, MP3],
    [{'event': 'task-failed', 'error_message': 'independent-secret'}],
    [{'event': 'task-started'}, MP3, {'event': 'task-failed', 'error_message': 'secret'}],
    [{'event': 'task-started', 'task_id': 'wrong'}],
    [MP3, {'event': 'task-finished'}],
    [{'event': 'task-started'}, b'<html>error</html>', {'event': 'task-finished'}],
    [TimeoutError('independent-secret')],
])
def test_failures_are_safe_closed_and_not_retried(monkeypatch, events):
    _, connection, calls = install(monkeypatch, events)
    with pytest.raises(tts_api.TTSRequestError) as caught:
        tts_api.synthesize(tts_api.resolve_tts_settings(config()), 'synthetic')
    assert 'secret' not in str(caught.value)
    assert connection.closed and len(calls) == 1


def test_audio_bound_and_total_deadline(monkeypatch):
    module, connection, _ = install(monkeypatch, [{'event': 'task-started'}, MP3, {'event': 'task-finished'}])
    monkeypatch.setattr(tts_api, 'MAX_AUDIO_BYTES', 10)
    with pytest.raises(tts_api.TTSRequestError):
        tts_api.synthesize(tts_api.resolve_tts_settings(config()), 'synthetic')
    assert connection.closed
    monkeypatch.setattr(tts_api, 'TOTAL_SECONDS', 0)
    with pytest.raises(tts_api.TTSRequestError):
        tts_api.synthesize(tts_api.resolve_tts_settings(config()), 'synthetic')


def test_frame_length_rejected_before_payload_read():
    module = helper()
    wire = io.BytesIO(b'\x82\x7f' + struct.pack('!Q', tts_api.MAX_LINE_BYTES + 1))
    frames = module._BoundedFrames(wire.read, False)
    with pytest.raises(tts_api.TTSRequestError):
        frames.recv_frame()
    assert wire.tell() == 10


@pytest.mark.parametrize('status', [101, 302, 307])
def test_handshake_headers_no_redirects_and_close(monkeypatch, status):
    module = helper()
    raw = types.SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(module, '_transport', lambda *_args: raw)
    connection = FakeSocket([], status)
    def connect(url, **options):
        assert url == config()['CHATVOICE_TTS_API_BASE']
        assert options['header'] == {'Authorization': 'Bearer sk-sp-independent-secret'}
        assert options['redirect_limit'] == 0
        connection.handshake_response = types.SimpleNamespace(status=status)
    connection.connect = connect
    monkeypatch.setattr(module, '_WebSocket', lambda: connection)
    if status == 101:
        assert module._open_socket(tts_api.resolve_tts_settings(config()), module.time.monotonic() + 60) is connection
        connection.shutdown()
    else:
        with pytest.raises(Exception):
            module._open_socket(tts_api.resolve_tts_settings(config()), module.time.monotonic() + 60)
    assert connection.closed


def test_cleanup_exception_cannot_leak_upstream_details(monkeypatch):
    _, connection, _ = install(monkeypatch, [TimeoutError('secret')])
    def close():
        connection.closed = True
        raise OSError('independent-secret')
    connection.shutdown = close
    with pytest.raises(tts_api.TTSRequestError) as caught:
        tts_api.synthesize(tts_api.resolve_tts_settings(config()), 'synthetic')
    assert 'secret' not in str(caught.value) and connection.closed


def test_fragmented_messages_and_malformed_json(monkeypatch):
    module, connection, _ = install(monkeypatch, [])
    def frames():
        task_id = connection.sent[0]['header']['task_id']
        started = json.dumps({'header': {'task_id': task_id, 'event': 'task-started'}}).encode()
        for opcode, fin, data in [(1, 0, started[:10]), (0, 1, started[10:]),
                                  (2, 0, MP3[:20]), (0, 1, MP3[20:]), (1, 1, b'bad-secret-json')]:
            yield types.SimpleNamespace(opcode=opcode, fin=fin, data=data, mask=0)
    events = frames()
    connection.recv_frame = lambda: next(events)
    with pytest.raises(tts_api.TTSRequestError) as caught:
        tts_api.synthesize(tts_api.resolve_tts_settings(config()), 'synthetic')
    assert 'secret' not in str(caught.value) and connection.closed
    assert len(connection.sent) == 3


def test_wire_size_and_slow_drip_deadline(monkeypatch):
    module = helper()
    clock = [0.0]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    class Raw:
        def settimeout(self, timeout):
            assert 0 < timeout <= 10
        def recv(self, size):
            clock[0] += 1
            return b'x' * min(size, 10)
    connection = module._DeadlineSocket(Raw(), 1)
    with pytest.raises(TimeoutError):
        connection.recv(100)
    clock[0] = 0
    monkeypatch.setattr(tts_api, 'MAX_RESPONSE_BYTES', 5)
    connection = module._DeadlineSocket(Raw(), 60)
    with pytest.raises(tts_api.TTSRequestError):
        connection.recv(100)


def test_trace_logging_refuses_connection_without_global_mutation(monkeypatch):
    module = helper()
    monkeypatch.setattr(module.websocket, 'isEnabledForTrace', lambda: True)
    monkeypatch.setattr(module, '_transport', lambda *_args: pytest.fail('must not connect while tracing'))
    with pytest.raises(tts_api.TTSRequestError):
        tts_api.synthesize(tts_api.resolve_tts_settings(config()), 'synthetic')
