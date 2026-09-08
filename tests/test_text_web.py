"""Public route contracts for independent notes/title endpoints."""
import importlib
import io
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

from chatvoice import text_api


@pytest.fixture
def app_module(monkeypatch, tmp_path):
    for name in list(os.environ):
        if name.startswith(('CHATVOICE_', 'OPENAI_')):
            monkeypatch.delenv(name)
    monkeypatch.setenv('CHATARCH_HOME', str(tmp_path / 'chatarch'))
    monkeypatch.setenv('CHATVOICE_HOME', str(tmp_path / 'voice'))
    monkeypatch.setenv('CHATVOICE_ASR_CHANNEL', 'stub-local')
    monkeypatch.setenv('CHATVOICE_ASR_PREWARM', '0')
    # Poison all old routes: independent requests must not touch any of them.
    monkeypatch.setenv('CHATVOICE_OPENAI_API_KEY', 'voice-secret')
    monkeypatch.setenv('CHATVOICE_OPENAI_API_MODEL', 'voice-model')
    monkeypatch.setenv('OPENAI_API_KEY', 'global-secret')
    monkeypatch.setenv('CHATVOICE_MEETING_NOTES_PROVIDER', 'crs-chat-completions')
    monkeypatch.setenv('CHATVOICE_MEETING_NOTES_CRS_PROFILE', 'missing-profile')
    for purpose in ('NOTES', 'TITLE'):
        monkeypatch.setenv(f'CHATVOICE_MEETING_{purpose}_API_BASE', f'https://{purpose.lower()}.example.test/api/plan/v3')
        monkeypatch.setenv(f'CHATVOICE_MEETING_{purpose}_API_KEY', f'{purpose.lower()}-secret')
        monkeypatch.setenv(f'CHATVOICE_MEETING_{purpose}_MODEL', f'{purpose.lower()}-model')
    name = 'chatvoice.web.legacy_app'
    sys.modules.pop(name, None)
    module = importlib.import_module(name)
    monkeypatch.setattr(module.urllib.request, 'urlopen', lambda *_a, **_k: pytest.fail('legacy network path used'))
    try:
        yield module
    finally:
        sys.modules.pop(name, None)


CASES = [('/api/meeting-notes/polish', {'transcript': '合成会议'}, 'notes'),
         ('/api/meeting-notes/revise/stream', {'transcript': '合成会议', 'current_summary': '旧纪要', 'instruction': '精简'}, 'notes'),
         ('/api/meeting-title', {'transcript': '合成会议'}, 'title')]


@pytest.mark.parametrize('route,body,purpose', CASES)
def test_independent_routes_use_only_their_own_standard_payload(app_module, monkeypatch, route, body, purpose):
    calls = []
    def fake_open(request, timeout):
        payload = json.loads(request.data)
        calls.append(payload)
        assert request.full_url == f'https://{purpose}.example.test/api/plan/v3/chat/completions'
        assert request.get_header('Authorization') == f'Bearer {purpose}-secret'
        assert payload['model'] == f'{purpose}-model'
        assert set(payload) <= {'model', 'messages', 'stream', 'max_tokens'}
        if payload.get('stream'):
            return io.BytesIO(('data: ' + json.dumps({'choices': [{'delta': {'content': '合成纪要'}}]}) + '\n\ndata: [DONE]\n\n').encode())
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': '合成会议主题'}, 'finish_reason': 'stop'}]}).encode())
    monkeypatch.setattr(text_api, '_open_request', fake_open)
    response = TestClient(app_module.app).post(route, json=body)
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    if 'stream' in route:
        assert 'event: done' in response.text and 'event: error' not in response.text
    else:
        assert response.json().get('content', response.json().get('title')) == '合成会议主题'
    assert 'secret' not in response.text


@pytest.mark.parametrize('route,body,purpose', [case for case in CASES if 'stream' not in case[0]])
@pytest.mark.parametrize('finish_fields', [
    pytest.param({'finish_reason': None}, id='null'),
    pytest.param({}, id='missing'),
    pytest.param({'finish_reason': 'length'}, id='length'),
    pytest.param({'finish_reason': 'content_filter'}, id='content-filter'),
    pytest.param({'finish_reason': 'tool_calls'}, id='tool-calls'),
    pytest.param({'finish_reason': 'unexpected'}, id='unknown'),
])
def test_blocking_routes_require_explicit_stop(app_module, monkeypatch, route, body, purpose, finish_fields):
    content = f'{purpose}-secret upstream body must not escape'
    upstream = {'choices': [{'message': {'content': content}, **finish_fields}]}
    monkeypatch.setattr(text_api, '_open_request', lambda *_a, **_k: io.BytesIO(json.dumps(upstream).encode()))
    response = TestClient(app_module.app).post(route, json=body)
    assert response.status_code == 502, response.text
    assert content not in response.text
    assert 'secret' not in response.text
    assert 'upstream body' not in response.text


@pytest.mark.parametrize('route,body,purpose', CASES)
@pytest.mark.parametrize('missing', ['API_BASE', 'API_KEY', 'MODEL'])
def test_partial_independent_configuration_is_http503_not_fallback(app_module, monkeypatch, route, body, purpose, missing):
    key = f'CHATVOICE_MEETING_{purpose.upper()}_{missing}'
    monkeypatch.setenv(key, '')
    monkeypatch.setitem(app_module._CHATVOICE_ENV, key, '')
    monkeypatch.setattr(text_api, '_open_request', lambda *_a, **_k: pytest.fail('partial configuration made network request'))
    response = TestClient(app_module.app).post(route, json={**body, 'model': 'request-cannot-repair-config'})
    assert response.status_code == 503, response.text
    assert 'CHATVOICE_MEETING_' in response.text
    assert 'secret' not in response.text


@pytest.mark.parametrize('route,body,purpose', CASES)
def test_upstream_error_redacted_and_never_done(app_module, monkeypatch, route, body, purpose):
    def fake_open(request, timeout):
        if 'stream' in route:
            return io.BytesIO(b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\ndata: {"error":{"message":"notes-secret dump"}}\n\n')
        return io.BytesIO(b'{"error":{"message":"title-secret dump"},"choices":[{"message":{"content":"fake success"}}]}')
    monkeypatch.setattr(text_api, '_open_request', fake_open)
    response = TestClient(app_module.app).post(route, json=body)
    assert 'secret' not in response.text and 'dump' not in response.text
    if 'stream' in route:
        assert 'event: error' in response.text and 'event: done' not in response.text
    else:
        assert response.status_code == 502


def test_status_separates_text_boundaries_and_retains_title_model(app_module, monkeypatch):
    client = TestClient(app_module.app)
    response = client.get('/api/status')
    assert response.status_code == 200
    payload = response.json()
    for purpose in ('notes', 'title'):
        assert payload[f'meeting_{purpose}'] == {
            'provider': 'chat-completions', 'model': f'{purpose}-model',
            'base_host': f'{purpose}.example.test', 'key_configured': True, 'configured': True}
    assert payload['meeting_title_model'] == 'title-model'
    assert 'secret' not in response.text and 'missing-profile' not in response.text
    monkeypatch.setenv('CHATVOICE_MEETING_TITLE_API_BASE', 'https://username:secret@title.example.test/v1?token=secret')
    partial = client.get('/api/status')
    assert partial.status_code == 200
    assert partial.json()['meeting_title']['configured'] is False
    assert 'secret' not in partial.text


def test_voice_gate_remains_unchanged_with_independent_text(app_module):
    response = TestClient(app_module.app).post('/api/tts', json={'text': 'test'})
    assert response.status_code == 503
    assert 'sk-sp' in response.text


def test_profile_only_independent_configuration_and_process_override(app_module, monkeypatch, tmp_path):
    from chatenv import EnvStore, get_paths
    from chatvoice.config import ChatVoiceConfig
    config = {}
    for purpose in ('NOTES', 'TITLE'):
        for suffix in ('API_BASE', 'API_KEY', 'MODEL'):
            key = f'CHATVOICE_MEETING_{purpose}_{suffix}'
            config[key] = os.environ[key]
            monkeypatch.delenv(key)
    EnvStore(get_paths().envs_dir).save_active(ChatVoiceConfig, config)
    sys.modules.pop('chatvoice.web.legacy_app', None)
    module = importlib.import_module('chatvoice.web.legacy_app')
    payload = TestClient(module.app).get('/api/status').json()
    assert payload['meeting_title']['base_host'] == 'title.example.test'
    monkeypatch.setenv('CHATVOICE_MEETING_TITLE_MODEL', 'override-title')
    assert TestClient(module.app).get('/api/status').json()['meeting_title_model'] == 'override-title'


def test_absent_independent_pairs_keep_legacy_models(app_module, monkeypatch):
    for purpose in ('NOTES', 'TITLE'):
        for suffix in ('API_BASE', 'API_KEY'):
            name = f'CHATVOICE_MEETING_{purpose}_{suffix}'
            monkeypatch.setenv(name, '')
            monkeypatch.setitem(app_module._CHATVOICE_ENV, name, '')
    monkeypatch.setattr(app_module, 'MEETING_NOTES_PROVIDER', 'token-plan-chat-completions')
    assert app_module._meeting_notes_provider() == 'token-plan-chat-completions'
    assert app_module._meeting_notes_model() == 'notes-model'
    assert app_module._meeting_title_model() == 'title-model'
