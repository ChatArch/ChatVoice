const { test } = require('node:test');
const { harness, json, assert, deferred } = require('./nonbrowser_harness.cjs');

test('Settings defaults to auto, preserves an explicit choice, and probes only on click', async () => {
  const app = harness();
  const channels = {
    default: 'auto', channels: {
      auto: { label: '自动（优先 Agent Plan）' },
      'volcengine-plan': { label: '火山 Agent Plan' },
      'funasr-gpu': { label: 'FunASR GPU' },
    }, stream_policy: {},
  };
  const health = { selected: 'auto', actual: 'funasr-gpu', fallback_reason: 'entitlement',
    plan: { state: 'unavailable', configured: true, functional: false, speech_verified: false } };
  app.respond = async (url, options) => {
    if (url === '/api/asr/channels') return json(channels);
    if (url === '/api/asr/health/probe') {
      assert.equal(options.method, 'POST');
      return json({ ...health, probe: { functional: false, speech_verified: false } });
    }
    if (url.startsWith('/api/asr/health')) return json(health);
    if (url === '/api/status') return json({ asr_health: { status: 'ready', recent: {} } });
    if (url === '/api/heartbeat') return json({ ok: true, asr: { status: 'ready', recent: {} } });
    return json({});
  };
  await app.run('refreshStatus()');
  assert.equal(app.element('asr-channel').value, 'auto');
  assert.match(app.element('asr-route-status').textContent, /funasr-gpu/);
  assert.match(app.element('asr-route-status').textContent, /entitlement/);
  assert.equal(app.requests.filter(item => item.url === '/api/asr/health/probe').length, 0);

  app.element('asr-channel').value = 'volcengine-plan';
  await app.element('asr-channel').dispatch('change');
  assert.equal(app.localValues.get('speakr.asr.channel.v1'), 'volcengine-plan');
  await app.run('refreshStatus()');
  assert.equal(app.element('asr-channel').value, 'volcengine-plan');
  await app.element('probe-asr-plan').click();
  assert.equal(app.requests.filter(item => item.url === '/api/asr/health/probe').length, 1);
});

test('Opening Settings refreshes cached route health without an active probe', async () => {
  const app = harness();
  app.element('asr-channel').value = 'auto';
  let state = 'stale';
  app.respond = async url => {
    assert.ok(url.startsWith('/api/asr/health?'));
    return json({ selected: 'auto', actual: 'volcengine-plan', plan: { configured: true, state } });
  };
  await app.run('refreshAsrRouteStatus()');
  assert.match(app.element('asr-route-status').textContent, /缓存待刷新/);
  state = 'healthy';
  await app.element('settings-menu').dispatch('click', { target: app.element('open-settings') });
  assert.equal(app.requests.length, 2, 'opening the dialog must read fresh cached health');
  await app.settle(() => app.element('asr-route-status').textContent.includes('可用'));
  assert.equal(app.requests.filter(item => item.method === 'POST').length, 0);
});

test('Plan and HTTP ASR key readiness use separate existing metadata', () => {
  const app = harness();
  const row = label => app.element('api-key-status-list').innerHTML.split('</li>').find(item => item.includes(label));
  app.run(`renderServerKeyStatus({ asr_channels: { 'volcengine-plan': { api_key_configured: true } }, asr_api: { url_configured: false }, api_keys: { asr_api_key_configured: false } })`);
  assert.match(row('Agent Plan ASR Key') || '', /class="ready">已配置/);
  assert.match(row('HTTP ASR API Key') || '', />未配置/);
  app.run(`renderServerKeyStatus({ asr_channels: { 'volcengine-plan': { api_key_configured: false } }, api_keys: { asr_api_key_configured: true } })`);
  assert.match(row('Agent Plan ASR Key') || '', />未配置/);
  assert.match(row('HTTP ASR API Key') || '', /class="ready">已配置/);
});

test('An older route read cannot overwrite a newer selected channel', async () => {
  const app = harness();
  const pending = deferred();
  app.respond = async url => url.includes('selected=auto') ? pending.promise : json({ selected: 'funasr-gpu', actual: 'funasr-gpu', plan: { configured: true, state: 'healthy' } });
  app.element('asr-channel').value = 'auto';
  const old = app.run('refreshAsrRouteStatus()');
  app.element('asr-channel').value = 'funasr-gpu';
  await app.run('refreshAsrRouteStatus()');
  pending.resolve(json({ selected: 'auto', actual: 'volcengine-plan', plan: { configured: true, state: 'stale' } }));
  await old;
  assert.match(app.element('asr-route-status').textContent, /实际 funasr-gpu/);
});

test('A manual Plan probe keeps the current fixed channel in route status', async () => {
  const app = harness();
  app.element('asr-channel').value = 'funasr-gpu';
  app.respond = async (url, options) => {
    if (url === '/api/asr/health/probe') {
      assert.equal(options.method, 'POST');
      return json({ selected: 'auto', actual: 'volcengine-plan', plan: { configured: true, state: 'healthy' }, probe: { functional: true } });
    }
    assert.ok(url.includes('selected=funasr-gpu'));
    return json({ selected: 'funasr-gpu', actual: 'funasr-gpu', plan: { configured: true, state: 'healthy' } });
  };
  await app.element('probe-asr-plan').click();
  assert.match(app.element('asr-route-status').textContent, /实际 funasr-gpu/);
  assert.equal(app.element('asr-channel').value, 'funasr-gpu');
  assert.equal(app.requests.filter(item => item.method === 'POST').length, 1);
});

test('Cached health reading bounds body consumption and clears its timer', async () => {
  const app = harness();
  let signal;
  let bodyStarted = false;
  app.respond = async (_url, options) => {
    signal = options.signal;
    return { ok: true, json: () => {
      bodyStarted = true;
      return new Promise((_resolve, reject) => {
        if (signal?.aborted) reject(new Error('body already aborted'));
        else signal?.addEventListener('abort', () => reject(new Error('body aborted')), { once: true });
      });
    } };
  };
  const reading = app.run('refreshAsrRouteStatus()');
  await app.settle(() => bodyStarted);
  assert.ok(signal, 'the complete read needs an abort signal');
  for (const callback of [...app.timers.values()]) callback();
  await reading;
  assert.equal(signal.aborted, true);
  assert.match(app.element('asr-route-status').textContent, /状态暂不可用/);
  assert.equal(app.timers.size, 0);
});

for (const interaction of ['reopen', 'change-selection']) {
  test(`Successful probe rereads current health after ${interaction} during its POST`, async () => {
    const app = harness();
    const pending = deferred();
    let state = 'stale';
    app.element('asr-channel').value = 'auto';
    app.respond = async url => {
      if (url === '/api/asr/health/probe') {
        await pending.promise;
        state = 'healthy';
        return json({ selected: 'auto', actual: 'volcengine-plan', plan: { configured: true, state }, probe: { functional: true } });
      }
      const selected = url.includes('selected=funasr-gpu') ? 'funasr-gpu' : 'auto';
      return json({ selected, actual: selected === 'auto' ? 'volcengine-plan' : selected, plan: { configured: true, state } });
    };
    const probing = app.element('probe-asr-plan').click();
    await app.settle(() => app.requests.some(item => item.url === '/api/asr/health/probe'));
    if (interaction === 'reopen') await app.element('settings-menu').dispatch('click', { target: app.element('open-settings') });
    else {
      app.element('asr-channel').value = 'funasr-gpu';
      await app.element('asr-channel').dispatch('change');
    }
    await app.settle(() => app.element('asr-route-status').textContent.includes('缓存待刷新'));
    pending.resolve();
    await probing;
    assert.match(app.element('asr-route-status').textContent, /、可用/);
    assert.equal(app.requests.filter(item => item.url.startsWith('/api/asr/health?')).length, 2);
    if (interaction === 'change-selection') assert.match(app.element('asr-route-status').textContent, /实际 funasr-gpu/);
    assert.equal(app.requests.filter(item => item.method === 'POST').length, 1);
  });
}
