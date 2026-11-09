const { test } = require('node:test');
const { harness, json, assert } = require('./nonbrowser_harness.cjs');

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
