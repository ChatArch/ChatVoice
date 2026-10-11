const { harness, assert } = require('./nonbrowser_harness.cjs');
(async () => {
  const app = harness();
  assert.equal(app.run("switchProductView('copilot')"), false);
  assert.equal(app.run('activeProductView'), 'meeting');
  assert.equal(await app.run('showCopilotPage()'), false);
  assert.equal(app.run('activeProductView'), 'meeting');
  assert.equal(app.requests.filter(request => request.url.startsWith('/api/copilot/')).length, 0);
  assert.equal(app.run("switchProductView('studio')"), true);
  assert.equal(app.run('activeProductView'), 'studio');
  assert.equal(app.run("switchProductView('conversation')"), true);
  assert.equal(app.run('activeProductView'), 'conversation');
  assert.equal(app.run("switchProductView('meeting')"), true);
  console.log('PASS copilot-retired');
})().catch(error => { console.error(error); process.exitCode = 1; });
