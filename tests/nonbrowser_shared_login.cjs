const {harness, assert} = require('./nonbrowser_harness.cjs');
(async () => {
  const app = harness();
  const test = process.argv[2];
  app.context.location.search = test === 'guest-return' ? '?mode=guest' : '';
  const moves = [];
  app.context.location.assign = url => moves.push(url);
  if (test === 'guest-return') {
    await app.run('bootstrapAccess()');
    assert.equal(app.run('storageMode'), 'guest');
    assert.ok(!app.element('entry-dialog').open);
    assert.equal(app.requests.length, 0, 'guest return must not contact cloud');
  } else if (test === 'save-before-login') {
    await app.run("activateStorageMode('guest')");
    app.run("appendTranscript('访客草稿'); syncSummaryContent('访客纪要'); todoMarkdown = '- [ ] 保留 Todo';");
    const id = app.run('activeMeetingId');
    await app.element('show-login').click();
    assert.deepEqual(moves, ['/login?next=%2F']);
    assert.match(app.stores.get('meetings').get(id).transcript_segments.map(x => x.text).join(''), /访客草稿/);
    assert.equal(app.run('storageMode'), 'guest');
    assert.equal(app.requests.length, 0);
  } else if (test === 'active-realtime') {
    app.run("storageMode='guest'; realtimeState='listening'");
    await app.element('show-login').click();
    assert.deepEqual(moves, []);
    assert.match(app.element('toast').textContent, /实时对话/);
  } else {
    app.run("storageMode='guest'; recorderState='recording'");
    await app.element('show-login').click();
    assert.deepEqual(moves, []);
    assert.match(app.element('toast').textContent, /录音/);
  }
  console.log('PASS ' + test);
})().catch(error => { console.error(error); process.exitCode=1; });
