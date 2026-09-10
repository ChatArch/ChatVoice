"""Shared renderer and real host handlers; synthetic legacy accounts only."""
from importlib.resources import files
import shutil
import subprocess
from pathlib import Path

import pytest
from test_chatlogin_auth import host, PASSWORD


def test_builtin_backend_type(host):
    from chatlogin.backends import ChatVoiceAuth, ChatVoiceSessionStore
    from chatvoice.web.auth_adapter import AuthAdapter, HostSessionStore
    app, _ = host
    assert AuthAdapter is ChatVoiceAuth
    assert HostSessionStore is ChatVoiceSessionStore
    assert type(app._AUTH) is ChatVoiceAuth
    assert type(app._AUTH.store) is ChatVoiceSessionStore


def test_shared_login_page_assets_and_customization(host, monkeypatch):
    from chatlogin.ui import LoginUI
    app, client = host
    page = client.get('/login?next=/')
    assert page.status_code == 200
    assert 'class="chatlogin__form"' in page.text
    assert 'name="username"' in page.text
    assert 'data-session-url="/api/auth/session"' in page.text
    assert 'href="/?mode=guest"' in page.text
    assert '受邀' in page.text
    for name, media in [('login.css', 'text/css'), ('login.js', 'javascript')]:
        response = client.get('/assets/chatlogin/' + name)
        assert response.status_code == 200
        assert media in response.headers['content-type']
        assert response.text == (files('chatlogin.web') / 'assets' / name).read_text()
    assert client.get('/assets/chatlogin/missing.js').status_code == 404
    assert '--cl-accent' in client.get('/assets/login-brand.css').text
    monkeypatch.setattr(app.app.state, 'login_ui', LoginUI(title='Custom <Brand>'))
    assert 'Custom &lt;Brand&gt;' in client.get('/login').text


@pytest.mark.parametrize('next_path', ['https://evil.invalid/', '//evil.invalid', '/\\evil.invalid', '/%2f%2fevil.invalid', '/%0aevil', '/%255cevil'])
def test_login_next_stays_local(host, next_path):
    _, client = host
    response = client.post('/api/auth/login', json={'username': 'alice@example.invalid', 'password': PASSWORD, 'next': next_path})
    assert response.status_code == 200
    assert response.json()['next'] == '/'
    assert 'data-next="/"' in client.get('/login', params={'next': next_path}).text


@pytest.mark.parametrize('key', ['account', 'username'])
def test_account_alias_cookie_and_local_next(host, key):
    _, client = host
    response = client.post('/api/auth/login', json={key: ' ALICE@EXAMPLE.INVALID ', 'password': PASSWORD, 'next': '/?tab=notes#draft', 'user_id': 'usr_bob', 'role': 'admin'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['user'] == {'id': 'usr_alice', 'account': 'alice@example.invalid', 'display_name': 'Alice'}
    assert payload['next'] == '/?tab=notes#draft'
    assert payload['csrf_token']
    cookie = response.headers['set-cookie']
    assert 'meeting_session=' in cookie and 'Max-Age=2592000' in cookie
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie


@pytest.mark.parametrize('case', ['guest-return', 'save-before-login', 'active-recording', 'active-realtime', 'failed-meeting-save', 'failed-conversation-save'])
def test_shared_login_host_controller(case):
    node = shutil.which('node')
    assert node, 'Node 22 required'
    result = subprocess.run([node, str(Path(__file__).with_name('nonbrowser_shared_login.cjs')), case], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines().count('PASS ' + case) == 1
