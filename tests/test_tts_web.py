import importlib
import json
from pathlib import Path
import sys
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from test_tts_api import MP3, Response, values


@pytest.fixture
def app_module(monkeypatch, tmp_path):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('CHATARCH_HOME', str(tmp_path / 'chatarch'))
    monkeypatch.setenv('CHATVOICE_HOME', str(tmp_path / 'voice'))
    monkeypatch.setenv('CHATVOICE_ASR_CHANNEL', 'stub-local')
    monkeypatch.setenv('CHATVOICE_ASR_PREWARM', '0')
    monkeypatch.setenv('CHATVOICE_OPENAI_API_KEY', 'unrelated-secret')
    for name, value in values('openai').items():
        monkeypatch.setenv(name, value)
    name = 'chatvoice.web.legacy_app'
    sys.modules.pop(name, None)
    module = importlib.import_module(name)
    monkeypatch.setattr(module, '_token_plan_key', lambda: pytest.fail('independent TTS borrowed legacy credential'))
    monkeypatch.setattr(module, '_fetch_models', lambda: {'count': 0, 'model_ids': []})
    yield module
    sys.modules.pop(name, None)


def test_web_dispatch_status_and_generic_headers(app_module, monkeypatch):
    module = importlib.import_module('chatvoice.tts_api')
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: Response(MP3))
    client = TestClient(app_module.app)
    result = client.post('/api/tts', json={'text': 'synthetic'})
    assert result.status_code == 200, result.text
    assert result.content == MP3
    assert result.headers['X-TTS-Provider'] == 'openai'
    assert result.headers['X-TTS-Model'] == 'custom-model'
    assert result.headers['X-TTS-Voice'] == 'speaker-one'
    assert 'x-qwen-model' not in result.headers
    assert 'secret' not in str(result.headers)
    status = client.get('/api/status').json()
    assert status['tts']['configured']
    assert status['tts_model'] == 'custom-model'
    assert status['realtime_model'] == app_module.REALTIME_MODEL
    assert 'secret' not in json.dumps(status)
    assert client.post('/api/tts', json={'text': 'synthetic', 'voice': 'speaker-two'}).headers['X-TTS-Voice'] == 'speaker-two'


def test_web_partial_503_and_upstream_502(app_module, monkeypatch):
    module = importlib.import_module('chatvoice.tts_api')
    monkeypatch.setattr(module, '_open_request', lambda *_a, **_k: Response(b'tts-secret error'))
    client = TestClient(app_module.app)
    result = client.post('/api/tts', json={'text': 'synthetic'})
    assert result.status_code == 502
    assert 'secret' not in result.text
    monkeypatch.setenv('CHATVOICE_TTS_API_KEY', '')
    monkeypatch.setitem(app_module._CHATVOICE_ENV, 'CHATVOICE_TTS_API_KEY', '')
    result = client.post('/api/tts', json={'text': 'synthetic'})
    assert result.status_code == 503
    assert not client.get('/api/status').json()['tts']['configured']


def test_profile_whitespace_cannot_silently_enable_legacy(app_module, monkeypatch):
    from chatvoice.config import ChatVoiceConfig
    config = {'CHATVOICE_TTS_API_KEY': ' '}
    for name in values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(app_module.EnvStore, 'load_active', lambda *_args: config)
    try:
        loaded = app_module._load_chatvoice_env_values()
        assert loaded['CHATVOICE_TTS_API_KEY'] == ' '
        assert not app_module.tts_api.tts_status(loaded)['configured']
    finally:
        ChatVoiceConfig.load_from_sources(override_values={name: '' for name in values()})


def test_ui_safe_dynamic_cards_and_clone_selection():
    source = (Path(__file__).resolve().parents[1] / 'src/chatvoice/web/static/index.html').read_text()
    from test_web_static_contract import _function_body
    body = _function_body(source, 'renderTtsVoices')
    assert 'createElement' in body and 'textContent' in body
    assert 'innerHTML' not in body
    assert "voiceSource === 'clone'" in body
    assert "card.id !== 'clone-voice-card'" in body
    assert 'status?.tts?.configured' in source
    assert "response.headers.get('X-TTS-Voice')" in source
    assert "$('voice-options').addEventListener('click'" in source


def test_dynamic_cards_execute_with_clone_preserved():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable for DOM contract execution')
    from test_web_static_contract import _function_body
    source = (Path(__file__).resolve().parents[1] / 'src/chatvoice/web/static/index.html').read_text()
    script = r'''
const assert = require('node:assert/strict');
let cards = [];
class Element {
  constructor() { this.dataset = {}; this.children = []; this.active = false;
    this.classList = {toggle: (name, active) => { this.active = active; }}; }
  append(...children) { this.children.push(...children); }
  remove() { cards = cards.filter(card => card !== this); }
}
const clone = new Element();
clone.id = 'clone-voice-card'; clone.dataset.voice = 'clone'; cards.push(clone);
const elements = {'clone-voice-card': clone};
const container = new Element();
container.querySelectorAll = () => [...cards];
container.insertBefore = (card, anchor) => cards.splice(cards.indexOf(anchor), 0, card);
elements['voice-options'] = container;
const $ = id => elements[id] || (elements[id] = new Element());
const document = {createElement: () => new Element(), querySelectorAll: () => [...cards]};
let selectedTtsVoice = 'speaker-two', voiceSource = 'clone', systemTtsKeyConfigured = true;
function updateVoiceSubmitState() {}
'''
    for name in ('selectTtsVoice', 'renderTtsVoices'):
        argument = 'voice' if name == 'selectTtsVoice' else 'status'
        script += f'function {name}({argument}) {{' + _function_body(source, name) + '}\n'
    script += r'''
const status = {tts: {voices: [{id:'speaker-one',label:'<img onerror=bad>'},
  {id:'speaker-two',label:'Second'}], default_voice:'speaker-one', model:'custom'}};
renderTtsVoices(status);
assert.equal(cards.length, 3);
assert.equal(cards[2], clone);
assert.equal(clone.active, true);
assert.equal(voiceSource, 'clone');
assert.equal(selectedTtsVoice, 'speaker-two');
assert.equal(cards[0].children[1].textContent, '<img onerror=bad>');
assert.equal($('clone-panel').hidden, false);
renderTtsVoices(status);
assert.equal(cards.length, 3);
assert.equal(cards[2], clone);
assert.equal(clone.active, true);
selectTtsVoice('speaker-two');
renderTtsVoices({tts:{voices:[{id:'new',label:'New'}],default_voice:'new'}});
assert.equal(selectedTtsVoice, 'new');
assert.equal(voiceSource, 'system');
assert.equal(cards[0].active, true);
assert.equal(cards[1], clone);
assert.equal($('clone-panel').hidden, true);
'''
    result = subprocess.run([node, '-e', script], text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
