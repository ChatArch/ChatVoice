import base64
import importlib
import io
import json
import struct
import urllib.error
import wave

import pytest


def api():
    return importlib.import_module('chatvoice.tts_api')


def values(provider='volcengine'):
    return {f'CHATVOICE_TTS_{key}': value for key, value in {
        'API_TYPE': provider, 'API_BASE': 'http://localhost:8000/custom/v3',
        'API_KEY': 'tts-secret', 'MODEL': 'custom-model', 'RESOURCE_ID': 'resource-id',
        'VOICES': json.dumps([{'id': 'speaker-one', 'label': '声音一'},
                              {'id': 'speaker-two', 'label': '声音二'}]),
    }.items()}


MP3 = b'\xff\xfb\x90\x00' + bytes(413)


def ndjson(*events):
    return ('\n'.join(json.dumps(event) for event in events) + '\n').encode()


def stream(audio=MP3):
    return ndjson({'code': 0, 'data': base64.b64encode(audio).decode()}, {'code': 20000000})


class Response(io.BytesIO):
    status = 200


def test_legacy_isolation_and_safe_config():
    module = api()
    assert module.resolve_tts_settings({'OPENAI_API_KEY': 'poison'}) is None
    settings = module.resolve_tts_settings(values())
    assert settings.base == 'http://localhost:8000/custom/v3'
    assert 'tts-secret' not in repr(settings)
    status = module.tts_status(values())
    assert status['default_voice'] == 'speaker-one'
    assert status['base_host'] == 'localhost'
    assert status['configured']
    assert 'secret' not in json.dumps(status)
    assert 'resource-id' not in json.dumps(status)


@pytest.mark.parametrize('field', ['API_TYPE', 'API_BASE', 'API_KEY', 'MODEL', 'RESOURCE_ID', 'VOICES'])
def test_partial_never_falls_back(field):
    module = api()
    config = values()
    config[f'CHATVOICE_TTS_{field}'] = ''
    with pytest.raises(module.TTSConfigurationError):
        module.resolve_tts_settings(config)
    assert not module.tts_status(config)['configured']
    with pytest.raises(module.TTSConfigurationError):
        module.resolve_tts_settings({f'CHATVOICE_TTS_{field}': values()[f'CHATVOICE_TTS_{field}']})


@pytest.mark.parametrize('field,value', [
    ('API_TYPE', 'unknown'), ('API_BASE', 'https://user:tts-secret@example.com'),
    ('API_BASE', 'https://example.com?key=tts-secret'), ('API_BASE', 'https://example.com#fragment'),
    ('API_BASE', 'https://example.com\r\nX-Key: tts-secret'), ('API_BASE', 'file:///tmp/test'),
    ('API_BASE', 'http://localhost:bad'), ('MODEL', 'model\nHeader: secret'),
    ('API_KEY', 'key\r\nHeader: secret'), ('RESOURCE_ID', 'id\nsecret'),
    ('API_KEY', ' '), ('MODEL', ' '), ('RESOURCE_ID', ' '),
    ('VOICES', 'invalid'), ('VOICES', '[]'), ('VOICES', '{}'),
    ('VOICES', '[{"id":"clone","label":"reserved"}]'),
    ('VOICES', '[{"id":"bad\\nvoice","label":"test"}]'),
    ('VOICES', '[{"id":"one","label":"a"},{"id":"one","label":"b"}]'),
    ('VOICES', '[{"id":"one","label":"a"},{"id":"two","label":"a"}]'),
    ('VOICES', '[{"id":"one","label":"<script>"}]'),
])
def test_invalid_configuration_safe(field, value):
    module = api()
    config = {**values(), f'CHATVOICE_TTS_{field}': value}
    with pytest.raises(module.TTSConfigurationError) as caught:
        module.resolve_tts_settings(config)
    assert 'secret' not in str(caught.value)
    assert 'secret' not in json.dumps(module.tts_status(config))


@pytest.mark.parametrize('provider', ['openai', 'volcengine'])
@pytest.mark.parametrize('output_format', ['mp3', 'wav'])
def test_protocol_payload_and_valid_audio(monkeypatch, provider, output_format):
    module = api()
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        output.writeframes(bytes(480))
    audio = MP3 if output_format == 'mp3' else buffer.getvalue()
    received = Response(stream(MP3 if output_format == 'mp3' else bytes(480)) if provider == 'volcengine' else audio)
    def fake_open(request, timeout):
        assert 0 < timeout <= 10
        payload = json.loads(request.data)
        if provider == 'volcengine':
            assert request.full_url.endswith('/custom/v3/tts/unidirectional')
            assert request.get_header('X-api-key') == 'tts-secret'
            assert request.get_header('X-api-resource-id') == 'resource-id'
            assert payload['req_params'] == {'text': 'synthetic', 'speaker': 'speaker-one',
                'audio_params': {'format': 'mp3' if output_format == 'mp3' else 'pcm', 'sample_rate': 24000}}
        else:
            assert request.full_url.endswith('/custom/v3/audio/speech')
            assert request.get_header('Authorization') == 'Bearer tts-secret'
            assert payload == {'model': 'custom-model', 'input': 'synthetic', 'voice': 'speaker-one', 'response_format': output_format}
        return received
    monkeypatch.setattr(module, '_open_request', fake_open)
    result = module.synthesize(module.resolve_tts_settings(values(provider)), 'synthetic', format=output_format)
    assert result['audio'] == audio
    assert result['provider'] == provider
    assert result['voice'] == 'speaker-one'
    assert received.closed


@pytest.mark.parametrize('body', [b'', ndjson({'code': 20000000}),
    ndjson({'code': 0, 'data': base64.b64encode(MP3).decode()}),
    ndjson({'code': 123, 'message': 'tts-secret'}), b'not json tts-secret\n',
    ndjson({'code': 0, 'data': '!invalid!'}, {'code': 20000000}),
    ndjson({'code': False, 'data': 'AA=='}, {'code': 20000000}),
    ndjson({'code': '0', 'data': 'AA=='}, {'code': 20000000}),
    ndjson({'code': 0, 'data': 12}, {'code': 20000000}),
    ndjson([]), stream(b'<html>tts-secret</html>'),
    stream() + ndjson({'code': 500, 'message': 'tts-secret'}),
])
def test_bad_streams_sanitized_and_closed(monkeypatch, body):
    module = api()
    received = Response(body)
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: received)
    with pytest.raises(module.TTSRequestError) as caught:
        module.synthesize(module.resolve_tts_settings(values()), 'synthetic')
    assert 'secret' not in str(caught.value)
    assert received.closed


@pytest.mark.parametrize('body', [b'', b'{"error":"tts-secret"}', b'<html>error</html>', b'ID3', MP3[:50]])
def test_openai_rejects_non_audio(monkeypatch, body):
    module = api()
    received = Response(body)
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: received)
    with pytest.raises(module.TTSRequestError):
        module.synthesize(module.resolve_tts_settings(values('openai')), 'synthetic')
    assert received.closed


@pytest.mark.parametrize('limit', ['MAX_RESPONSE_BYTES', 'MAX_LINE_BYTES', 'MAX_AUDIO_BYTES'])
def test_bounds(monkeypatch, limit):
    module = api()
    monkeypatch.setattr(module, limit, 10)
    received = Response(stream())
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: received)
    with pytest.raises(module.TTSRequestError):
        module.synthesize(module.resolve_tts_settings(values()), 'synthetic')
    assert received.closed


@pytest.mark.parametrize('status', [301, 302, 307, 401, 500])
def test_http_status_and_redirect_policy(monkeypatch, status):
    module = api()
    received = Response(stream())
    received.status = status
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: received)
    with pytest.raises(module.TTSRequestError):
        module.synthesize(module.resolve_tts_settings(values()), 'synthetic')
    assert received.closed
    assert module._NoRedirect().redirect_request(None, None, status, '', {}, 'https://other.test') is None


def test_timeout_and_unknown_voice(monkeypatch):
    module = api()
    def fail(*args, **kwargs):
        raise TimeoutError('tts-secret')
    monkeypatch.setattr(module, '_open_request', fail)
    with pytest.raises(module.TTSRequestError, match='语音'):
        module.synthesize(module.resolve_tts_settings(values()), 'synthetic')
    with pytest.raises(module.TTSConfigurationError):
        module.synthesize(module.resolve_tts_settings(values()), 'synthetic', voice='unknown')


def test_probe_selected_chatenv_home(monkeypatch, tmp_path):
    from click.testing import CliRunner
    from chatenv import EnvStore, get_paths
    from chatenv.cli import cli
    from chatvoice.config import ChatVoiceConfig
    module = api()
    config = values('openai')
    ChatVoiceConfig.load_from_sources(override_values={field.env_key: '' for field in ChatVoiceConfig.get_fields().values()})
    EnvStore(get_paths(tmp_path).envs_dir).save_active(ChatVoiceConfig, config)
    calls = []
    def fake_open(request, timeout):
        calls.append(json.loads(request.data))
        return Response(MP3)
    monkeypatch.setattr(module, '_open_request', fake_open)
    try:
        result = CliRunner().invoke(cli, ['--home', str(tmp_path), 'test', '-t', 'chatvoice', '-I'])
        assert result.exit_code == 0, result.output
        assert len(calls) == 1
        assert calls[0]['voice'] == 'speaker-one'
        assert 'secret' not in result.output
        monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: Response(b'bad'))
        result = CliRunner().invoke(cli, ['--home', str(tmp_path), 'test', '-t', 'chatvoice', '-I'])
        assert result.exit_code != 0
    finally:
        ChatVoiceConfig.load_from_sources(override_values={name: '' for name in config})


def test_total_deadline_and_read_cleanup(monkeypatch):
    module = api()
    clock = [0.0]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    class SlowResponse(Response):
        def read1(self, size):
            clock[0] += module.TOTAL_SECONDS + 1
            return super().read1(size)
    received = SlowResponse(stream())
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: received)
    with pytest.raises(module.TTSRequestError):
        module.synthesize(module.resolve_tts_settings(values()), 'synthetic')
    assert received.closed


def test_http_error_body_is_closed_and_never_exposed(monkeypatch):
    module = api()
    body = io.BytesIO(b'tts-secret')
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError('https://tts-secret@example.test', 401, 'tts-secret', {}, body)
    monkeypatch.setattr(module, '_open_request', fail)
    with pytest.raises(module.TTSRequestError) as caught:
        module.synthesize(module.resolve_tts_settings(values()), 'synthetic')
    assert body.closed
    assert 'tts-secret' not in str(caught.value)


def test_openai_needs_no_resource_and_probe_is_cpu_only(monkeypatch):
    import sys
    module = api()
    config = values('openai')
    config['CHATVOICE_TTS_RESOURCE_ID'] = ''
    assert module.resolve_tts_settings(config).resource_id == ''
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: Response(MP3))
    imported = set(sys.modules)
    assert module.probe_tts_configuration(config)['voice'] == 'speaker-one'
    assert not any(name.startswith(('chatvoice.web', 'torch', 'funasr', 'dashscope')) for name in set(sys.modules) - imported)
    assert module.probe_tts_configuration({}) is None


@pytest.mark.parametrize('voices', [
    [{'id': str(number), 'label': str(number)} for number in range(65)],
    [{'id': 'a' * 81, 'label': 'label'}], [{'id': 'voice', 'label': 'a' * 81}],
    [{'id': 'voice', 'label': 'bad\x7flabel'}], [{'id': 'voice', 'label': None}],
])
def test_voice_bounds(voices):
    module = api()
    with pytest.raises(module.TTSConfigurationError):
        module.resolve_tts_settings({**values(), 'CHATVOICE_TTS_VOICES': json.dumps(voices)})


@pytest.mark.parametrize('body', [b'RIFF\x00\x00\x00\x00WAVE', MP3, MP3 + b'\x00', b'\x00', b'{"error":true} ', b'<html>error</html>'])
def test_invalid_wav(monkeypatch, body):
    module = api()
    received = Response(body)
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: received)
    with pytest.raises(module.TTSRequestError):
        module.synthesize(module.resolve_tts_settings(values('openai')), 'synthetic', format='wav')
    assert received.closed


@pytest.mark.parametrize('sample', [-1, 123, 91, 60])
def test_pcm_first_sample_is_not_a_magic_prefix(monkeypatch, sample):
    module = api()
    audio = struct.pack('<h', sample) + bytes(478)
    received = Response(stream(audio))
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: received)
    result = module.synthesize(module.resolve_tts_settings(values()), 'synthetic', format='wav')
    with wave.open(io.BytesIO(result['audio']), 'rb') as output:
        assert (output.getnchannels(), output.getsampwidth(), output.getframerate()) == (1, 2, 24000)
        assert output.readframes(output.getnframes()) == audio
    assert received.closed


@pytest.mark.parametrize('body', [b'', b'\x00', MP3, bytes(482)])
def test_invalid_pcm_size_and_alignment(monkeypatch, body):
    module = api()
    monkeypatch.setattr(module, 'MAX_AUDIO_BYTES', 480)
    received = Response(stream(body))
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: received)
    with pytest.raises(module.TTSRequestError):
        module.synthesize(module.resolve_tts_settings(values()), 'synthetic', format='wav')
    assert received.closed


def test_redirects_exercise_real_opener(monkeypatch):
    import email.message
    import urllib.request
    import urllib.response
    module = api()
    calls = []
    class RedirectTransport(urllib.request.HTTPHandler):
        def http_open(self, request):
            calls.append(request.full_url)
            headers = email.message.Message()
            headers['Location'] = 'http://elsewhere.test/stolen'
            result = urllib.response.addinfourl(io.BytesIO(b''), headers, request.full_url, 307)
            result.msg = 'Redirect'
            return result
    opener = urllib.request.build_opener(module._NoRedirect(), RedirectTransport())
    monkeypatch.setattr(module, '_open_request', lambda request, timeout: opener.open(request, timeout=timeout))
    with pytest.raises(module.TTSRequestError):
        module.synthesize(module.resolve_tts_settings(values('openai')), 'synthetic')
    assert calls == ['http://localhost:8000/custom/v3/audio/speech']


def test_deadline_covers_drip_fed_http_headers(monkeypatch):
    module = api()
    clock = [0.0]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    class DripReader(io.BytesIO):
        def read1(self, size):
            clock[0] += 1
            return super().read1(min(size, 1))
    class Socket:
        def settimeout(self, timeout):
            assert 0 < timeout <= 3
    reader = module._DeadlineReader(DripReader(b'HTTP/1.1 200 OK\r\n'), Socket(), 3)
    with pytest.raises(TimeoutError):
        reader.readline(65536)
    assert clock[0] <= 3


@pytest.mark.parametrize('scheme', ['http', 'https'])
@pytest.mark.parametrize('provider', ['openai', 'volcengine'])
@pytest.mark.parametrize('framing', ['chunked', 'content-length', 'no-length', 'premature-eof'])
def test_real_http_parser_with_mock_socket(monkeypatch, scheme, provider, framing):
    module = api()
    body = MP3 if provider == 'openai' else stream()
    if framing == 'chunked':
        wire = b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'
        for offset in range(0, len(body), 37):
            chunk = body[offset:offset + 37]
            wire += f'{len(chunk):x}\r\n'.encode() + chunk + b'\r\n'
        wire += b'0\r\n\r\n'
    else:
        length = len(body) * (2 if framing == 'premature-eof' else 1)
        header = b'' if framing == 'no-length' else f'Content-Length: {length}\r\n'.encode()
        wire = b'HTTP/1.1 200 OK\r\n' + header + b'\r\n' + body
    class Socket:
        def __init__(self):
            self.reader = io.BytesIO(wire)
            self.closed = False
            self.sent = []
        def makefile(self, *args):
            return self.reader
        def settimeout(self, timeout):
            assert 0 < timeout <= module.IO_SECONDS
        def sendall(self, data):
            self.sent.append(data)
        def close(self):
            self.closed = True
    socket = Socket()
    def connect(connection):
        connection.sock = socket
    monkeypatch.setattr(module.http.client.HTTPConnection, 'connect', connect)
    monkeypatch.setattr(module.http.client.HTTPSConnection, 'connect', connect)
    config = {**values(provider), 'CHATVOICE_TTS_API_BASE': f'{scheme}://localhost:8000/custom/v3'}
    if framing == 'premature-eof':
        with pytest.raises(module.TTSRequestError) as caught:
            module.synthesize(module.resolve_tts_settings(config), 'synthetic')
        assert str(caught.value) == module.REQUEST_ERROR
    else:
        result = module.synthesize(module.resolve_tts_settings(config), 'synthetic')
        assert result['audio'] == MP3
    assert socket.closed and socket.reader.closed
    assert b'POST /custom/v3/' in socket.sent[0]


def test_dns_resolution_obeys_total_deadline(monkeypatch):
    import threading
    import time
    module = api()
    release = threading.Event()
    finished = threading.Event()
    def delayed_lookup(*args):
        try:
            release.wait(1)
            return []
        finally:
            finished.set()
    monkeypatch.setattr(module.socket, 'getaddrinfo', delayed_lookup)
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            module._resolve_addresses('synthetic.test', 443, started + 0.02)
        assert time.monotonic() - started < 0.5
    finally:
        release.set()
        finished.wait(1)


def test_documented_sentence_metadata_and_safe_usage(monkeypatch):
    module = api()
    body = ndjson({'code': 0, 'data': base64.b64encode(MP3).decode()},
                  {'code': 0, 'data': None, 'sentence': {'text': 'synthetic', 'words': []}},
                  {'code': 20000000, 'data': None, 'usage': {'text_words': 10, 'unknown': 'tts-secret'}})
    received = Response(body)
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: received)
    result = module.synthesize(module.resolve_tts_settings(values()), 'synthetic')
    assert result['audio'] == MP3
    assert result['usage'] == {'text_words': 10}
    assert received.closed
