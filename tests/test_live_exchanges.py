"""Execute the live verifier with HTTP, WebSocket and process boundaries offline."""
import asyncio
import base64
import copy
import json
import socket
from types import SimpleNamespace
import wave

import httpx
import pytest
import websockets

from test_live_acceptance_contract import verifier


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('Offline tests must not open sockets')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)


class FakeSocket:
    def __init__(self, events):
        self.events = iter(events)
        self.sent = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def recv(self):
        return json.dumps(next(self.events))

    async def send(self, payload):
        self.sent.append(payload)


def boundary(monkeypatch, events):
    connection = FakeSocket(events)
    monkeypatch.setattr(websockets, 'connect', lambda *args, **kwargs: connection)
    return connection


def probe(monkeypatch, module, container='mp3', codec='mp3'):
    calls = []
    def process(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            'format': {'duration': '1.0', 'format_name': container},
            'streams': [{'codec_type': 'audio', 'codec_name': codec}],
        }))
    monkeypatch.setattr(module.subprocess, 'run', process)
    return calls


def client_boundary(monkeypatch, *, config=None, headers=None, revision=None):
    requests = []
    status = {'tts': {'provider': 'volcengine', 'model': 'voice-model',
                      'voices': [{'id': 'voice-one'}]}, 'token_plan_key': True,
              'realtime_model': 'realtime-model'}
    def handler(request):
        requests.append(request)
        path = request.url.path
        if path == '/api/status':
            return httpx.Response(200, json=status)
        if path == '/api/asr/channels':
            return httpx.Response(200, json=config)
        if path == '/':
            return httpx.Response(200, text='<select id="conversation-voice"><option value="voice-one">v</option></select><textarea id="tts-text">hello</textarea>')
        if path == '/api/tts':
            payload = json.loads(request.content)
            if not payload['text']:
                return httpx.Response(422)
            fmt = payload['format']
            actual = {'content-type': 'audio/mpeg' if fmt == 'mp3' else 'audio/wav',
                      'x-tts-provider': 'volcengine', 'x-tts-model': 'voice-model',
                      'x-tts-voice': payload['voice']}
            for key, value in (headers or {}).items():
                if value is None:
                    actual.pop(key, None)
                else:
                    actual[key] = value
            return httpx.Response(200, headers=actual, content=b'boundary-audio')
        if path.endswith('/revise/stream'):
            text = revision if revision is not None else '[[[CANVAS]]]notes[[[REPLY]]]ok'
            return httpx.Response(200, text='event: delta\ndata: '+json.dumps({'text': text})+'\n\nevent: done\ndata: {}\n\n')
        return httpx.Response(200, json={'content': 'notes', 'title': 'title'})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(handler)))
    return requests


def asr_events():
    events = [{'demo_event': 'asr.stream.'+kind, 'channel': 'api-server',
               'context_seconds': 45} for kind in ('ready', 'started')]
    for window in (1, 2):
        events.extend([
            {'demo_event': 'asr.stream.result', 'result': {
                'channel': 'api-server', 'raw_text': 'recognized',
                'meta': {'engine': 'api', 'status_code': 200},
                'stream': {'window_index': window, 'chunk_index': window,
                           'revision': window, 'final': True}}},
            {'demo_event': 'asr.stream.done', 'final': window == 2,
             'rollover': window == 1, 'window_index': 2},
        ])
    return events


@pytest.mark.parametrize('defect', [None, 'stub', 'mock', 'ready', 'started', 'channel',
    'engine', 'missing-engine', 'missing-resumed', 'empty-resumed', 'window',
    'chunk', 'revision', 'result-final', 'rollover', 'done-window', 'oversized', 'empty'])
def test_asr_transport_contract(monkeypatch, tmp_path, defect):
    module = verifier()
    events = asr_events()
    config = {'default': 'api-server', 'channels': {'api-server': {'engine': 'api'}},
              'stream_policy': {'context_seconds': 45}}
    if defect in ('stub', 'mock'):
        channel = defect+'-local'
        config = {'default': channel, 'channels': {channel: {'engine': defect}}}
        for event in events:
            if 'channel' in event:
                event['channel'] = channel
            if 'result' in event:
                event['result']['channel'] = channel
                event['result']['meta']['engine'] = defect
    if defect in ('ready', 'started'):
        events[0 if defect == 'ready' else 1]['channel'] = 'stub-local'
    if defect == 'channel':
        events[4]['result']['channel'] = 'funasr-cpu'
    if defect == 'engine':
        events[4]['result']['meta']['engine'] = 'stub'
    if defect == 'missing-engine':
        events[4]['result']['meta'].clear()
    if defect == 'missing-resumed':
        del events[4]
    if defect == 'empty-resumed':
        events[4]['result']['raw_text'] = ' '
    for name, key, value in [('window', 'window_index', 1), ('chunk', 'chunk_index', 1),
                             ('revision', 'revision', 1), ('result-final', 'final', False)]:
        if defect == name:
            events[4]['result']['stream'][key] = value
    if defect == 'rollover':
        events[3]['rollover'] = False
    if defect == 'done-window':
        events[3]['window_index'] = 1
    connection = boundary(monkeypatch, events)
    requests = client_boundary(monkeypatch, config=config)
    probe(monkeypatch, module)
    audio = tmp_path/'input.wav'
    with wave.open(str(audio), 'wb') as output:
        output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        output.writeframes(b'\0\0' * (0 if defect == 'empty' else 16000 * (46 if defect == 'oversized' else 1)))
    receipt = module.run('https://service.invalid', tmp_path, audio=audio)
    case = next(case for case in receipt['cases'] if case['id'] == 'asr-pause-resume-finish')
    assert case['status'] == ('pass' if defect is None else 'fail')
    if defect in ('stub', 'mock', 'ready', 'started', 'oversized', 'empty'):
        assert not any(isinstance(frame, bytes) for frame in connection.sent)
    if defect is None:
        assert any(request.url.path == '/api/asr/channels' for request in requests)
        assert case['evidence']['segments'][1]['meta']['engine'] == 'api'
        assert connection.closed
        assert receipt.get('real_provider_calls') is not True


@pytest.mark.parametrize('field', ['x-tts-provider', 'x-tts-model', 'x-tts-voice', 'content-type'])
@pytest.mark.parametrize('value', [None, 'wrong', 'audio/ogg'])
def test_tts_rejects_wrong_or_missing_headers(monkeypatch, tmp_path, field, value):
    module = verifier()
    client_boundary(monkeypatch, headers={field: value})
    probe(monkeypatch, module)
    receipt = module.run('https://service.invalid', tmp_path)
    assert all(case['status'] == 'fail' for case in receipt['cases']
               if case['id'] in ('tts-0-mp3', 'tts-0-wav', 'tts-untouched-ui-text'))


@pytest.mark.parametrize('fmt,container,codec,valid', [
    ('mp3', 'mp3', 'mp3', True), ('wav', 'wav', 'pcm_s16le', True),
    ('mp3', 'wav', 'pcm_s16le', False), ('wav', 'mp3', 'mp3', False),
    ('mp3', 'mp3', 'aac', False), ('wav', 'wav', 'mp3', False),
    ('mp3', '', 'mp3', False), ('wav', 'wav', '', False),
])
def test_tts_checks_actual_container_and_codec(monkeypatch, tmp_path, fmt, container, codec, valid):
    module = verifier()
    client_boundary(monkeypatch)
    calls = probe(monkeypatch, module, container, codec)
    receipt = module.run('https://service.invalid', tmp_path)
    case = next(case for case in receipt['cases'] if case['id'] == 'tts-0-'+fmt)
    assert case['status'] == ('pass' if valid else 'fail')
    if valid:
        assert case['evidence']['provider'] == 'volcengine'
        assert case['evidence']['model'] == 'voice-model'
        assert case['evidence']['voice'] == 'voice-one'
        assert case['evidence']['container'] == container
        assert case['evidence']['codec'] == codec
        assert any('format_name' in ' '.join(command) for command in calls)


def realtime_events():
    session = {'model': 'realtime-model', 'voice': 'voice-one', 'modalities': ['text', 'audio'],
               'instructions': '用简短中文回答，只说你好。', 'input_audio_format': 'pcm',
               'output_audio_format': 'pcm', 'max_history_turns': 20,
               'turn_detection': {'type': 'server_vad', 'threshold': .5, 'silence_duration_ms': 700}}
    return [
        {'demo_event': 'proxy.connected'},
        {'demo_event': 'upstream.event', 'event': {'type': 'session.updated', 'session': session}},
        {'demo_event': 'upstream.event', 'event': {'type': 'response.created', 'response': {'id': 'reply-1'}}},
        {'demo_event': 'transcript.delta', 'role': 'assistant', 'text': 'hello'},
        {'demo_event': 'audio.delta', 'audio': base64.b64encode(b'\0\0'*24000).decode()},
        {'demo_event': 'upstream.event', 'event': {'type': 'response.done', 'response': {'id': 'reply-1', 'status': 'completed'}}},
    ]


def test_realtime_forwarded_events_retain_response_correlation(monkeypatch, tmp_path):
    module = verifier()
    events = realtime_events()
    events[4]['response_id'] = 'reply-1'
    events.insert(4, {'demo_event': 'upstream.event', 'event': {
        'type': 'response.audio_transcript.delta', 'response_id': 'reply-1', 'delta': 'hello'}})
    events.insert(6, {'demo_event': 'upstream.event', 'event': {
        'type': 'response.audio.delta', 'response_id': 'reply-1', 'delta': '<audio omitted>'}})
    connection = boundary(monkeypatch, events)
    probe(monkeypatch, module, 'wav', 'pcm_s16le')
    evidence = asyncio.run(module.realtime_exchange('https://service.invalid', 'realtime-model', 'voice-one', tmp_path))
    assert evidence['response_id'] == 'reply-1'
    assert evidence['text_chars'] == 5
    assert connection.closed
    assert [json.loads(frame)['type'] for frame in connection.sent] == [
        'session.update', 'conversation.item.create', 'response.create']


@pytest.mark.parametrize('channel,engine', [('api-server', 'api'), ('funasr-gpu', 'funasr'), ('funasr-cpu', 'funasr')])
def test_asr_uses_deployed_channel_configuration(monkeypatch, tmp_path, channel, engine):
    module = verifier()
    events = asr_events()
    for event in events:
        if 'channel' in event:
            event['channel'] = channel
        if 'result' in event:
            event['result']['channel'] = channel
            event['result']['meta']['engine'] = engine
    connection = boundary(monkeypatch, events)
    client_boundary(monkeypatch, config={'default': channel, 'channels': {channel: {'engine': engine}}})
    probe(monkeypatch, module)
    audio = tmp_path/'input.wav'
    with wave.open(str(audio), 'wb') as output:
        output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        output.writeframes(b'\0\0'*16000)
    receipt = module.run('https://service.invalid', tmp_path, audio=audio)
    case = next(case for case in receipt['cases'] if case['id'] == 'asr-pause-resume-finish')
    assert case['status'] == 'pass'
    assert case['evidence']['expected_channel'] == channel
    assert case['evidence']['expected_engine'] == engine
    assert json.loads(connection.sent[0])['channel'] == channel
    assert [segment['stream']['window_index'] for segment in case['evidence']['segments']] == [1, 2]


@pytest.mark.parametrize('defect', [None, 'missing-response', 'missing-status', 'wrong-id',
    'missing-id', 'no-created', 'prior-created', 'prior-audio', 'prior-text', 'second-created',
    'foreign-event', 'no-audio', 'no-text', 'ack-model', 'ack-voice', 'ack-modalities',
    'ack-input_audio_format', 'ack-output_audio_format', 'ack-turn_detection',
    'ack-instructions', 'ack-max_history_turns', 'ack-missing-session'])
def test_realtime_transport_contract(monkeypatch, tmp_path, defect):
    module = verifier()
    events = realtime_events()
    if defect == 'missing-response':
        del events[-1]['event']['response']
    if defect in ('missing-status', 'missing-id'):
        del events[-1]['event']['response'][defect.removeprefix('missing-')]
    if defect == 'wrong-id':
        events[-1]['event']['response']['id'] = 'foreign'
    if defect == 'no-created':
        del events[2]
    if defect == 'prior-created':
        events.insert(1, events.pop(2))
    if defect in ('prior-audio', 'prior-text'):
        events.insert(1, events.pop(4 if defect == 'prior-audio' else 3))
    if defect == 'second-created':
        events.insert(3, copy.deepcopy(events[2]))
    if defect == 'foreign-event':
        events.insert(3, {'demo_event': 'upstream.event', 'event': {
            'type': 'response.audio.delta', 'response_id': 'foreign', 'delta': '<omitted>'}})
    if defect in ('no-audio', 'no-text'):
        del events[4 if defect == 'no-audio' else 3]
    if defect and defect.startswith('ack-'):
        if defect == 'ack-missing-session':
            del events[1]['event']['session']
        else:
            events[1]['event']['session'][defect.removeprefix('ack-')] = 'wrong'
    connection = boundary(monkeypatch, events)
    probe(monkeypatch, module, 'wav', 'pcm_s16le')
    if defect is None:
        evidence = asyncio.run(module.realtime_exchange('https://service.invalid', 'realtime-model', 'voice-one', tmp_path))
        assert evidence['response_id'] == 'reply-1'
        assert evidence['session']['model'] == 'realtime-model'
    else:
        with pytest.raises(ValueError):
            asyncio.run(module.realtime_exchange('https://service.invalid', 'realtime-model', 'voice-one', tmp_path))
    assert connection.closed


@pytest.mark.parametrize('text', ['[[[REPLY]]]ok[[[CANVAS]]]notes',
    '[[[CANVAS]]]notes[[[REPLY]]] ', '[[[CANVAS]]]notes[[[REPLY]]]ok[[[CANVAS]]]extra'])
def test_revision_rejects_bad_markers_over_http(monkeypatch, tmp_path, text):
    module = verifier()
    client_boundary(monkeypatch, revision=text)
    probe(monkeypatch, module)
    receipt = module.run('https://service.invalid', tmp_path)
    revisions = [case for case in receipt['cases'] if case['id'].startswith('revision-')]
    assert len(revisions) == 4
    assert all(case['status'] == 'fail' for case in revisions)


def test_realtime_plan_denial_is_blocked_over_transport(monkeypatch, tmp_path):
    module = verifier()
    client_boundary(monkeypatch)
    probe(monkeypatch, module)
    boundary(monkeypatch, [{'demo_event': 'upstream.event', 'event': {
        'type': 'error', 'error': {'code': 'AccessDenied.Unpurchased', 'message': 'secret'}}}])
    receipt = module.run('https://service.invalid', tmp_path, include_realtime=True)
    assert receipt['cases'][-1]['status'] == 'blocked'
    assert receipt['cases'][-1]['error_code'] == 'AccessDenied.Unpurchased'
    assert module.result_exit_code(receipt['cases']) == 1
    assert 'secret' not in (tmp_path/'receipt.json').read_text()
