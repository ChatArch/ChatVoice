const {harness, assert, json} = require('./nonbrowser_harness.cjs');
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
  } else if (test.startsWith('txn-')) {
    await app.run("activateStorageMode('guest')");
    const conversation = test.includes('conversation');
    if (conversation) app.run("activeMeetingId=null; ensureActiveConversation(); realtimeMessages=[{role:'user',text:'未提交的对话',final:true}]");
    else app.run("appendTranscript('未提交的访客草稿')");
    const id = app.run(conversation ? 'activeConversationId' : 'activeMeetingId');
    const store = app.stores.get(conversation ? 'conversations' : 'meetings');
    const before = structuredClone(store.get(id));
    app.transactionControl.holdWrites = true;
    const count = app.transactions.length;
    const work = app.element('show-login').click();
    await app.settle(() => app.transactions.slice(count).some(tx => tx.mode === 'readwrite' && tx.requestSucceeded));
    const tx = app.transactions.slice(count).find(tx => tx.mode === 'readwrite');
    assert.equal(tx.completed, false);
    assert.deepEqual(moves, [], 'request success must not navigate before transaction commit');
    if (test.endsWith('abort')) {
      tx.abort(); await work;
      assert.deepEqual(moves, []);
      assert.deepEqual(store.get(id), before, 'aborted transaction must not change committed data');
      assert.match(app.element('toast').textContent, /事务中止/);
    } else {
      tx.commit(); await work;
      assert.deepEqual(moves, ['/login?next=%2F']);
      assert.ok(store.get(id));
    }
  } else if (test.startsWith('failed-')) {
    app.run("storageMode='account'; authUser={id:'fixture'}; csrfToken='fixture'");
    if (test === 'failed-meeting-save') app.run("ensureActiveMeeting(); appendTranscript('Unsaved draft');");
    else app.run("ensureActiveConversation();");
    app.respond = async () => json({detail:'Synthetic save failure'}, 500);
    await app.element('show-login').click();
    assert.deepEqual(moves, [], 'failed persistence must prevent navigation');
    assert.match(app.element('toast').textContent, /保存失败/);
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
