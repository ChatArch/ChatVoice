"""Independent text boundaries; all upstream traffic is synthetic/mocked."""
import importlib
import io
import json
import sys
import urllib.error

import pytest

from chatvoice.config import ChatVoiceConfig


def values(purpose='notes'):
    prefix = f'CHATVOICE_MEETING_{purpose.upper()}'
    return {f'{prefix}_API_BASE': f'https://{purpose}.example.test/api/plan/v3',
            f'{prefix}_API_KEY': f'{purpose}-secret', f'{prefix}_MODEL': f'{purpose}-model'}


def load_text_api():
    assert importlib.util.find_spec('chatvoice.text_api') is not None, 'Independent text helper missing'
    return importlib.import_module('chatvoice.text_api')


def test_typed_independent_text_fields():
    fields = ChatVoiceConfig.get_fields()
    for purpose in ('NOTES', 'TITLE'):
        for suffix in ('API_BASE', 'API_KEY'):
            name = f'CHATVOICE_MEETING_{purpose}_{suffix}'
            assert name in fields
            assert not fields[name].default
        assert fields[f'CHATVOICE_MEETING_{purpose}_API_KEY'].is_sensitive


@pytest.mark.parametrize('purpose', ['notes', 'title'])
def test_resolve_never_borrows_other_credentials_or_model(purpose):
    text_api = load_text_api()
    config = values(purpose)
    config.update(CHATVOICE_OPENAI_API_KEY='voice-secret', CHATVOICE_OPENAI_API_MODEL='voice-model',
                  OPENAI_API_KEY='global-secret', OPENAI_API_MODEL='global-model',
                  CHATVOICE_MEETING_NOTES_CRS_API_KEY='crs-secret')
    settings = text_api.resolve_text_settings(config, purpose)
    assert settings.base == f'https://{purpose}.example.test/api/plan/v3'
    assert settings.key == f'{purpose}-secret'
    assert settings.model == f'{purpose}-model'
    assert 'secret' not in repr(settings)
    for suffix in ('API_BASE', 'API_KEY', 'MODEL'):
        incomplete = dict(config)
        incomplete.pop(f'CHATVOICE_MEETING_{purpose.upper()}_{suffix}')
        with pytest.raises(text_api.TextConfigurationError):
            text_api.resolve_text_settings(incomplete, purpose, req_model='request-model')
    assert text_api.resolve_text_settings({'CHATVOICE_OPENAI_API_KEY': 'voice-secret'}, purpose) is None
    assert text_api.resolve_text_settings({f'CHATVOICE_MEETING_{purpose.upper()}_MODEL': 'legacy'}, purpose) is None


@pytest.mark.parametrize('base', ['file:///secret', 'https://user:password@example.test/v1',
                                  'https://example.test/v1?token=secret', 'https://example.test/v1#secret', 'https://[bad'])
def test_invalid_base_fails_without_exposing_values(base):
    text_api = load_text_api()
    config = values()
    config['CHATVOICE_MEETING_NOTES_API_BASE'] = base
    with pytest.raises(text_api.TextConfigurationError) as caught:
        text_api.resolve_text_settings(config, 'notes')
    assert base not in str(caught.value)
    status = text_api.text_status(config, 'notes')
    assert not status['configured']
    assert 'password' not in json.dumps(status)
    assert 'secret' not in json.dumps(status)


def test_complete_standard_request(monkeypatch):
    text_api = load_text_api()
    calls = []
    def fake_open(request, timeout):
        calls.append((request, timeout))
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': '合成标题'}, 'finish_reason': 'stop'}], 'usage': {'total_tokens': 3}}).encode())
    monkeypatch.setattr(text_api, '_open_request', fake_open)
    settings = text_api.resolve_text_settings(values('title'), 'title')
    result = text_api.complete_text(settings, [{'role': 'user', 'content': 'synthetic'}], timeout=30, max_tokens=64)
    assert result['content'] == '合成标题'
    request, timeout = calls[0]
    assert request.full_url == 'https://title.example.test/api/plan/v3/chat/completions'
    assert request.get_header('Authorization') == 'Bearer title-secret'
    assert timeout == 30
    assert json.loads(request.data) == {'model': 'title-model', 'messages': [{'role': 'user', 'content': 'synthetic'}], 'max_tokens': 64}


@pytest.mark.parametrize('body', [
    {'error': {'message': 'title-secret upstream dump'}, 'choices': [{'message': {'content': 'fake success'}}]},
    {'choices': [{'message': {'content': ''}, 'finish_reason': 'stop'}]}, {'choices': [{'message': {'content': '   '}, 'finish_reason': 'stop'}]},
    {'choices': [{'message': {'content': None, 'reasoning_content': 'not final'}, 'finish_reason': 'stop'}]},
    {'choices': [{'message': {'content': ['not text']}, 'finish_reason': 'stop'}]}, {}, ['invalid'],
    {'choices': [{'message': {'content': 'truncated'}, 'finish_reason': 'length'}]},
    {'choices': [{'message': {'content': 'filtered'}, 'finish_reason': 'content_filter'}]},
])
def test_bad_200_response_is_not_success(monkeypatch, body):
    text_api = load_text_api()
    monkeypatch.setattr(text_api, '_open_request', lambda *_a, **_k: io.BytesIO(json.dumps(body).encode()))
    with pytest.raises(text_api.TextRequestError) as caught:
        text_api.complete_text(text_api.resolve_text_settings(values('title'), 'title'), [])
    assert 'title-secret' not in str(caught.value)
    assert 'upstream dump' not in str(caught.value)


@pytest.mark.parametrize('finish_fields', [
    pytest.param({'finish_reason': None}, id='null'),
    pytest.param({}, id='missing'),
    pytest.param({'finish_reason': 'length'}, id='length'),
    pytest.param({'finish_reason': 'content_filter'}, id='content-filter'),
    pytest.param({'finish_reason': 'tool_calls'}, id='tool-calls'),
    pytest.param({'finish_reason': 'unexpected'}, id='unknown'),
])
def test_complete_requires_explicit_stop(monkeypatch, finish_fields):
    text_api = load_text_api()
    content = 'title-secret upstream body must not escape'
    body = {'choices': [{'message': {'content': content}, **finish_fields}]}
    monkeypatch.setattr(text_api, '_open_request', lambda *_a, **_k: io.BytesIO(json.dumps(body).encode()))
    with pytest.raises(text_api.TextRequestError) as caught:
        text_api.complete_text(text_api.resolve_text_settings(values('title'), 'title'), [])
    assert content not in str(caught.value)
    assert 'title-secret' not in str(caught.value)
    assert 'upstream body' not in str(caught.value)


def stream_bytes(*events):
    return io.BytesIO(''.join(f'data: {json.dumps(event, ensure_ascii=False)}\n\n' if not isinstance(event, str)
                            else f'data: {event}\n\n' for event in events).encode())


def test_stream_standard_payload_and_deltas(monkeypatch):
    text_api = load_text_api()
    def fake_open(request, timeout):
        assert json.loads(request.data) == {'model': 'notes-model', 'messages': [], 'stream': True}
        return stream_bytes({'choices': [{'delta': {'role': 'assistant'}}]},
                            {'choices': [{'delta': {'content': '合成'}}]},
                            {'choices': [{'delta': {'content': '纪要'}, 'finish_reason': 'stop'}]}, '[DONE]')
    monkeypatch.setattr(text_api, '_open_request', fake_open)
    assert ''.join(text_api.stream_text(text_api.resolve_text_settings(values(), 'notes'), [])) == '合成纪要'


@pytest.mark.parametrize('events', [[], ['[DONE]'],
    [{'choices': [{'delta': {'content': ' '}}]}, '[DONE]'],
    [{'choices': [{'delta': {'content': 'partial'}}]}, {'error': {'message': 'notes-secret'}}],
    [{'choices': [{'delta': {'content': 'partial'}}]}, 'malformed notes-secret'],
    [{'error': {'message': 'notes-secret'}}],
    [{'choices': [{'delta': {'content': 'partial'}}]}],
])
def test_stream_error_empty_or_truncated_never_completes(monkeypatch, events):
    text_api = load_text_api()
    monkeypatch.setattr(text_api, '_open_request', lambda *_a, **_k: stream_bytes(*events))
    with pytest.raises(text_api.TextRequestError) as caught:
        list(text_api.stream_text(text_api.resolve_text_settings(values(), 'notes'), []))
    assert 'notes-secret' not in str(caught.value)


@pytest.mark.parametrize('stream', [False, True])
def test_http_failure_redacted(monkeypatch, stream):
    text_api = load_text_api()
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError('https://secret@host', 401, 'notes-secret', {}, io.BytesIO(b'notes-secret body'))
    monkeypatch.setattr(text_api, '_open_request', fail)
    settings = text_api.resolve_text_settings(values(), 'notes')
    with pytest.raises(text_api.TextRequestError) as caught:
        list(text_api.stream_text(settings, [])) if stream else text_api.complete_text(settings, [])
    assert 'secret' not in str(caught.value)


def test_chatenv_hook_synthetic_requests_and_no_web_import(monkeypatch, capsys):
    text_api = load_text_api()
    config = {**values(), **values('title')}
    ChatVoiceConfig.load_from_sources(override_values=config)
    calls = []
    def fake_open(request, timeout):
        payload = json.loads(request.data)
        calls.append(payload)
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': '合成内容'}, 'finish_reason': 'stop'}]}).encode())
    monkeypatch.setattr(text_api, '_open_request', fake_open)
    imported = set(sys.modules)
    try:
        ChatVoiceConfig.test()
        assert [p['model'] for p in calls] == ['notes-model', 'title-model']
        assert all(p['messages'] and p['max_tokens'] == 64 for p in calls)
        assert not any(m.startswith(('chatvoice.web', 'torch', 'funasr')) for m in set(sys.modules) - imported)
        assert 'secret' not in capsys.readouterr().out
    finally:
        ChatVoiceConfig.load_from_sources(override_values={name: '' for name in config})


def test_chatenv_cli_loads_selected_home(monkeypatch, tmp_path):
    from click.testing import CliRunner
    from chatenv import EnvStore, get_paths
    from chatenv.cli import cli
    text_api = load_text_api()
    config = {**values(), **values('title')}
    ChatVoiceConfig.load_from_sources(override_values={name: '' for name in config})
    EnvStore(get_paths(tmp_path).envs_dir).save_active(ChatVoiceConfig, config)
    calls = []
    def fake_open(request, timeout):
        calls.append(json.loads(request.data)['model'])
        return io.BytesIO(b'{"choices":[{"message":{"content":"OK"},"finish_reason":"stop"}]}')
    monkeypatch.setattr(text_api, '_open_request', fake_open)
    result = CliRunner().invoke(cli, ['--home', str(tmp_path), 'test', '-t', 'chatvoice', '-I'])
    try:
        assert result.exit_code == 0, result.output
        assert calls == ['notes-model', 'title-model'], result.output
        assert 'secret' not in result.output
    finally:
        ChatVoiceConfig.load_from_sources(override_values={name: '' for name in config})


def test_chatenv_hook_legacy_schema_only(monkeypatch, capsys):
    text_api = load_text_api()
    config = {k: '' for k in {**values(), **values('title')}}
    ChatVoiceConfig.load_from_sources(override_values=config)
    monkeypatch.setattr(text_api, '_open_request', lambda *_a, **_k: pytest.fail('legacy config must not call network'))
    ChatVoiceConfig.test()
    assert 'Schema' in capsys.readouterr().out


def test_chatenv_hook_partial_config_fails_before_any_probe(monkeypatch):
    text_api = load_text_api()
    config = {**values(), **values('title')}
    config['CHATVOICE_MEETING_TITLE_API_KEY'] = ''
    ChatVoiceConfig.load_from_sources(override_values=config)
    monkeypatch.setattr(text_api, '_open_request', lambda *_a, **_k: pytest.fail('validate both before network'))
    try:
        with pytest.raises(text_api.TextConfigurationError):
            ChatVoiceConfig.test()
    finally:
        ChatVoiceConfig.load_from_sources(override_values={name: '' for name in config})
