const {harness, assert} = require('./nonbrowser_harness.cjs');
let completed = false;
process.once('beforeExit', () => {
  if (!completed) {
    console.error('Realtime controller case did not complete');
    process.exitCode = 1;
  }
});
(async () => {
  const app = harness();
  app.run("storageMode = 'guest'");
  await app.element('conversation-main').click();
  await app.settle(() => app.sockets.length > 0);
  const socket = app.sockets[0];
  await socket.open();
  const message = '当前实时模型套餐未开通或已失效';
  socket.message({demo_event:'proxy.error',error_type:'AccessDenied.Unpurchased',message});
  socket.close();
  assert.equal(app.run('realtimeState'), 'error');
  assert.equal(app.element('conversation-status').querySelector('span').textContent, message,
    'socket close must preserve the actionable provider error');
  assert.ok(app.tracks.every(track => track.stopped));
  assert.ok(app.graphs.every(graph => graph.closed));
  console.log('PASS provider error survives close and resources are released');
})().then(() => { completed = true; }).catch(error => {
  completed = true;
  console.error(error);
  process.exitCode = 1;
});
