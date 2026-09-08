"""Regression for actual Token Plan errors outside the usual type=error envelope."""
import asyncio
import json
import pytest
from test_nonbrowser_routes import flows_app


def test_realtime_controller_preserves_provider_error_after_close():
    import shutil
    import subprocess
    from pathlib import Path
    node=shutil.which('node')
    assert node, 'Node.js is required for actual controller regression'
    result=subprocess.run([node,str(Path(__file__).with_name('nonbrowser_realtime_error.cjs'))],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('code,expected', [
    ('AccessDenied.Unpurchased','套餐'),
    ('InvalidApiKey','鉴权'),
    ('QuotaExceeded','额度'),
    ('SomeUnknownProviderFailure','实时服务'),
])
def test_realtime_flat_provider_error_is_actionable_sanitized_and_closes(flows_app, monkeypatch, code, expected):
    module=flows_app
    output=[];closed=[]
    class Client:
        query_params={}
        async def accept(self): pass
        async def send_json(self, value): output.append(value)
        async def send_text(self, value): output.append(value)
        async def receive(self): await asyncio.Event().wait()
        async def close(self, **kwargs): closed.append('client')
    class Upstream:
        def __aiter__(self): return self.events()
        async def events(self):
            yield json.dumps({'code':code,'message':'credential secret-sentinel must not be relayed','request_id':'private-request'})
        async def send(self, value): pass
        async def close(self): closed.append('upstream')
    async def connect(*args): return Upstream()
    monkeypatch.setattr(module,'_token_plan_key',lambda:'offline')
    monkeypatch.setattr(module,'_connect_upstream',connect)
    async def run():
        await asyncio.wait_for(module.realtime_proxy(Client()),timeout=3)
        # Cancelled peer pump must have been awaited/settled before return.
        await asyncio.sleep(0)
    asyncio.run(run())
    errors=[x for x in output if isinstance(x,dict) and x.get('demo_event')=='proxy.error']
    assert len(errors)==1, 'Flat provider errors must not disappear into an opaque close'
    assert expected in errors[0]['message']
    assert 'secret-sentinel' not in json.dumps(output)
    assert sorted(closed)==['client','upstream']
