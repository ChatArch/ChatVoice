"""Fail-closed contracts for the opt-in, non-browser live acceptance runner."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]

def verifier():
    path = ROOT / 'scripts' / 'verify_service.py'
    assert path.exists(), 'An explicit reusable non-browser live acceptance command is required'
    spec = importlib.util.spec_from_file_location('live_verifier', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('body', [
    'event: error\ndata: {"message":"failed"}\n\n',
    'event: delta\ndata: {"text":"partial"}\n\n',
    'event: done\ndata: {}\n\n',
    'event: delta\ndata: {"text":"[[[CANVAS]]]summary[[[REPLY]]]ok"}\n\nevent: error\ndata: {}\n\nevent: done\ndata: {}\n\n',
])
def test_sse_success_requires_complete_nonempty_canvas_without_error(body):
    with pytest.raises(ValueError):
        verifier().checked_revision(body)

def test_sse_success_uses_actual_delta_framing():
    body = 'event: delta\ndata: {"text":"[[[CANVAS]]]summary[[[REPLY]]]ok"}\n\nevent: done\ndata: {"model":"model"}\n\n'
    assert verifier().checked_revision(body) == '[[[CANVAS]]]summary[[[REPLY]]]ok'

@pytest.mark.parametrize('payload', [
    {'code':'AccessDenied.Unpurchased','message':'secret-sentinel'},
    {'demo_event':'proxy.error','error_type':'AccessDenied.Unpurchased','message':'secret-sentinel'},
])
def test_live_plan_denial_is_blocked_and_never_includes_raw_provider_text(payload):
    module=verifier()
    with pytest.raises(module.ProviderFailure) as caught:
        module.raise_provider_error(payload)
    assert caught.value.blocked is True
    assert caught.value.code=='AccessDenied.Unpurchased'
    assert 'secret-sentinel' not in str(caught.value)


@pytest.mark.parametrize('statuses,expected', [(['pass'],0),(['pass','fail'],1),(['pass','blocked'],1),([],1),(['not_run'],1)])
def test_live_exit_code_does_not_hide_failure_or_missing_coverage(statuses,expected):
    assert verifier().result_exit_code([{'status':s} for s in statuses]) == expected

def test_live_calls_require_explicit_opt_in(tmp_path):
    with pytest.raises(SystemExit) as e:
        verifier().main(['--url','https://service.invalid','--out',str(tmp_path)])
    assert e.value.code != 0

@pytest.mark.parametrize('value',['../foreign','', 'a/b', 'x?token=secret', 'x#fragment'])
def test_clone_job_ids_cannot_redirect_cleanup(value):
    with pytest.raises(ValueError):
        verifier().checked_job_id(value)


def test_clone_preflight_rejects_non_test_accounts_before_login(tmp_path):
    class NoNetwork:
        def post(self, *a, **kw):
            raise AssertionError('preflight must not touch the network')
    with pytest.raises(ValueError):
        verifier().clone_exchange(NoNetwork(), tmp_path/'unused.wav', 'real-user', 'secret', tmp_path)


def test_live_voice_is_read_from_the_deployed_markup_not_guessed():
    html = '<select id="conversation-voice"><option value="first">a</option><option value="chosen" selected>b</option></select><textarea id="tts-text">你好&amp;世界</textarea>'
    assert verifier().read_ui_defaults(html) == {'voice': 'chosen', 'text': '你好&世界'}


def test_missing_live_ui_contract_fails_closed():
    with pytest.raises(ValueError):
        verifier().read_ui_defaults('<html></html>')


@pytest.mark.parametrize('url',['http://service.invalid','https://user:secret@service.invalid','https://service.invalid/?token=secret','https://service.invalid/#fragment'])
def test_target_cannot_leak_credentials_or_send_them_over_http(url):
    with pytest.raises(ValueError):
        verifier().checked_target(url)
