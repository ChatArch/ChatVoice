const { harness, json, audio, sse, deferred, assert } = require('./nonbrowser_harness.cjs');

function meeting(mutation) {
  const app = harness(mutation);
  app.respond = async url => { if (url === '/api/heartbeat') return json({ ok: true }); throw new Error(`Unexpected request ${url}`); };
  app.run("storageMode = 'guest'; resetSession({ persist: false }); appendTranscript('合成会议讨论行动计划。'); syncSummaryContent('原纪要'); hasGeneratedSummary = true; summaryIsDemo = false;");
  return app;
}

const cases = {
  async access(mode = 'success') {
    const app = harness();
    app.respond = async (url, options) => {
      if (url === '/api/auth/login') return json(mode === 'failure' ? {detail: '拒绝'} : {user: {id: 'offline', display_name: 'Offline'}, csrf_token: 'csrf'}, mode === 'failure' ? 401 : 200);
      if (url === '/api/meetings') return json({meetings: []});
      if (url === '/api/conversations') return json({conversations: []});
      if (url === '/api/auth/logout') { assert.equal(options.headers['X-CSRF-Token'], 'csrf'); return json({authenticated: false}); }
      if (url === '/api/auth/session') return json({authenticated: false});
      if (url === '/api/tokens') return json({tokens: []});
      throw new Error(`Unexpected request ${url}`);
    };
    await app.run('bootstrapAccess()');
    assert.ok(app.element('entry-dialog').open);
    app.element('auth-account').value = 'offline@example.test';
    app.element('auth-password').value = 'offline-password';
    await app.element('auth-form').dispatch('submit');
    assert.equal(app.element('auth-submit').disabled, false);
    if (mode === 'failure') { assert.equal(app.run('storageMode'), null); assert.match(app.element('auth-message').textContent, /拒绝/); return; }
    assert.equal(app.run('storageMode'), 'account');
    assert.equal(app.run('csrfToken'), 'csrf');
    await app.element('account-action').click();
    assert.equal(app.run('storageMode'), 'guest');
    assert.equal(app.run('authUser'), null);
    assert.equal(app.run('csrfToken'), '');
    assert.equal(app.element('api-token-output').textContent, '');
    app.run("storageMode = 'account'");
    app.respond = async () => json({}, 401);
    await assert.rejects(app.run('getStoredMeeting("expired")'), /登录已过期/);
  },
  async asrFinish() {
    const app = meeting();
    app.respond = async url => url === '/api/heartbeat' ? json({ok: true}) : json({content: '结束摘要', title: '结束标题'});
    await app.element('record-toggle').click();
    const socket = app.sockets[0];
    await socket.open();
    for (const [text, revision, final] of [['第一句。', 1, false], ['第一句。第二句。', 2, true]]) socket.message({demo_event: 'asr.stream.result', result: {corrected_text: text, stream: {revision_scope: 'window', replace: true, revision, final}}});
    assert.match(app.run('transcriptText()'), /第一句。\s*第二句。/);
    assert.equal(app.run('transcriptText().split("第一句").length'), 2);
    await app.element('record-toggle').click();
    socket.message({demo_event: 'asr.stream.done', final: false});
    assert.equal(app.run('pauseCommitPending'), false);
    assert.equal(app.run('asrWindowCommitPending'), false);
    await app.element('record-toggle').click();
    await app.element('finish-recording').click();
    socket.message({demo_event: 'asr.stream.done', final: true});
    await app.settle(() => !app.run('summaryRunning'));
    await app.run('saveActiveMeeting()');
    assert.equal(app.run('recorderState'), 'ended');
    assert.ok(socket.closed);
    assert.equal(app.run('finishFallbackTimer'), null);
    assert.equal(app.run('summaryContent()'), '结束摘要');
    assert.match(app.stores.get('meetings').get(app.run('activeMeetingId')).transcript_segments.map(item => item.text).join(''), /第二句/);
  },
  async title(mode = 'success') {
    const app = meeting();
    const pending = deferred();
    app.respond = () => pending.promise;
    app.run('ensureActiveMeeting()');
    const work = app.run("generateMeetingTitle(transcriptText(), {force: true, explicit: true})");
    if (mode === 'late') await app.run('createNewMeeting()');
    if (mode === 'manual') { app.element('meeting-title').value = '手工标题'; await app.element('meeting-title').dispatch('input'); }
    pending.resolve(json(mode === 'empty' ? {} : { title: '自动标题' }, mode === 'failure' ? 502 : 200));
    await work;
    assert.equal(app.element('refresh-title').disabled, false);
    if (mode === 'success') assert.equal(app.element('meeting-title').value, '自动标题');
    else if (mode === 'manual') assert.equal(app.element('meeting-title').value, '手工标题');
    else assert.notEqual(app.element('meeting-title').value, '自动标题');
  },
  async clone(mode = 'success') {
    const app = harness();
    app.run("storageMode = 'account'; authUser = {id: 'offline'}; csrfToken = 'csrf'; localVoiceCloneStatus = {configured: true, ok: true}; selectTtsVoice('clone')");
    app.element('tts-text').value = '合成文字';
    if (mode === 'guest') app.run("storageMode = 'guest'; authUser = null");
    if (mode !== 'noReference') {
      app.element('clone-reference-file').files = [new Blob(['reference'], { type: 'audio/wav' })];
      await app.element('clone-reference-file').dispatch('change');
    }
    app.element('clone-consent').checked = mode !== 'noConsent';
    await app.element('clone-consent').dispatch('change');
    const pending = deferred();
    app.respond = async (url, options) => {
      if (url === '/api/voice-clone/status') return json({configured: true, ok: true});
      if (mode === 'staleCreate' && options.method === 'POST') return pending.promise;
      if (options.method === 'POST') return json({ job_id: 'offline-job' }, 202);
      if (mode === 'staleAudio' && url.endsWith('/audio')) return pending.promise;
      if (url.endsWith('/audio')) return audio('clone', 'audio/wav');
      if (mode === 'stale') return pending.promise;
      if (mode === 'failed') return json({ status: 'failed', error_message: 'offline failed' });
      if (mode === 'poll' && app.requests.filter(item => item.url.endsWith('/offline-job')).length === 1) return json({status: 'running', progress: .5});
      return json({ status: 'ready', engine: 'offline' });
    };
    const work = app.element('synthesize-voice').click();
    if (['stale', 'staleCreate', 'staleAudio'].includes(mode)) {
      await app.settle(() => app.requests.length === (mode === 'staleCreate' ? 1 : mode === 'staleAudio' ? 3 : 2));
      const previousReference = app.run('cloneReferenceUrl');
      app.run('setCloneReference(null)');
      assert.ok(app.revoked.includes(previousReference));
      assert.equal(app.run('cloneJobPollTimer'), null);
      pending.resolve(mode === 'staleAudio' ? audio() : json({ status: 'ready', job_id: 'stale-job' }));
    }
    await work;
    if (mode === 'poll') {
      assert.equal(app.run('cloneGenerating'), true);
      const timer = app.run('cloneJobPollTimer');
      assert.ok(app.timers.has(timer));
      await app.timers.get(timer)();
    }
    assert.equal(app.run('cloneGenerating'), false);
    if (['guest', 'noReference', 'noConsent'].includes(mode)) assert.equal(app.requests.length, 0);
    else if (mode === 'failed' || mode.startsWith('stale')) assert.equal(app.run('ttsAudioUrl'), null, 'stale/failed clone must not publish audio');
    else {
      assert.equal(app.element('result-player').hidden, false);
      assert.equal(app.requests[0].headers['X-CSRF-Token'], 'csrf');
      assert.equal(app.requests[0].body.get('text'), '合成文字');
      await app.element('download-voice').click();
      assert.ok(app.downloads.at(-1).download.endsWith('.wav'));
      const old = app.run('cloneReferenceUrl');
      await app.element('record-clone-reference').click();
      assert.equal(app.run('cloneRecorder.state'), 'recording');
      await app.element('record-clone-reference').click();
      assert.equal(app.run('cloneReferenceName'), 'recorded-reference.webm');
      assert.ok(app.tracks.every(track => track.stopped));
      assert.ok(app.revoked.includes(old));
      assert.equal(app.stores.size, 0);
    }
    await app.run('refreshVoiceCloneStatus()');
    assert.equal(app.run('voiceSource'), 'clone');
    assert.ok(app.element('clone-voice-card').classList.contains('active'));
  },
  async realtime(mode = 'success') {
    const app = harness();
    app.run("storageMode = 'guest'");
    if (mode === 'micFailure') app.context.navigator.mediaDevices.getUserMedia = async () => { throw new Error('offline device failure'); };
    await app.element('conversation-main').click();
    await app.settle(() => app.sockets.length || app.run('realtimeState') === 'error');
    if (mode === 'micFailure') {
      assert.equal(app.run('realtimeState'), 'error');
      assert.ok(app.graphs.every(graph => graph.closed));
      return;
    }
    const socket = app.sockets[0];
    await socket.open();
    if (mode === 'connectFailure') {
      socket.onerror();
      socket.close();
      assert.equal(app.run('realtimeState'), 'error');
      assert.ok(app.tracks.every(track => track.stopped));
      assert.ok(app.graphs.every(graph => graph.closed), 'connection failure closes both audio contexts');
      return;
    }
    socket.message({ demo_event: 'proxy.connected' });
    assert.equal(socket.sent[0].type, 'session.update');
    socket.message({ demo_event: 'upstream.event', event: { type: 'session.updated' } });
    assert.equal(app.run('realtimeState'), 'listening');
    app.run('realtimeInputProcessor.onaudioprocess({inputBuffer: {getChannelData: () => new Float32Array([.1,.2,.3,.4])}})');
    assert.equal(socket.sent.at(-1).type, 'input_audio_buffer.append');
    await app.element('conversation-mute').click();
    assert.equal(app.run('realtimeState'), 'muted');
    const sent = socket.sent.length;
    app.run('realtimeInputProcessor.onaudioprocess({inputBuffer: {getChannelData: () => new Float32Array([.1,.2])}})');
    assert.equal(socket.sent.length, sent);
    await app.element('conversation-mute').click();
    assert.equal(app.run('realtimeState'), 'listening');
    app.run("sendRealtimeTextPrompt('合成问题')");
    assert.equal(socket.sent.at(-1).type, 'response.create');
    for (const [phase, text] of [['delta', '合成'], ['delta', '合成回复'], ['final', '合成回复']]) socket.message({ demo_event: 'transcript.delta', role: 'assistant', phase, text, source_type: 'response.audio_transcript.done' });
    assert.equal(app.run('realtimeMessages.length'), 2);
    assert.match(app.element('conversation-messages').innerHTML, /合成回复/);
    socket.message({ demo_event: 'audio.delta', audio: 'AAABAA==' });
    assert.equal(app.run('realtimeOutputSources.size'), 1);
    socket.message({ demo_event: 'upstream.event', event: { type: 'response.done' } });
    await app.element('conversation-end').click();
    assert.equal(app.run('realtimeState'), 'ended');
    assert.equal(app.run('realtimeOutputSources.size'), 0);
    assert.ok(socket.closed);
    assert.ok(app.tracks.every(track => track.stopped));
    assert.ok(app.graphs.every(graph => graph.closed));
    await app.run('saveActiveConversation()');
    const id = app.run('activeConversationId');
    assert.equal(app.stores.get('conversations').get(id).messages[1].text, '合成回复');
    await app.element('conversation-export').click();
    assert.ok(app.downloads.at(-1).download.endsWith('.md'));
    await app.run('createNewConversation()');
    await app.run(`openConversation(${JSON.stringify(id)})`);
    assert.equal(app.run('realtimeMessages[1].text'), '合成回复');
    await app.run(`deleteConversationRecord(${JSON.stringify(id)})`);
    assert.ok(!app.stores.get('conversations').has(id));
  },
  async meeting() {
    const app = meeting();
    app.element('meeting-title').value = '合成项目';
    await app.element('meeting-title').dispatch('input');
    app.run("setMeetingTags(['thought', 'thought', '项目']);");
    await app.run('saveActiveMeeting()');
    const id = app.run('activeMeetingId');
    assert.equal(app.stores.get('meetings').get(id).title, '合成项目');
    assert.deepEqual(app.stores.get('meetings').get(id).tags, ['thought', '项目']);
    await app.run('createNewMeeting()');
    await app.run(`openMeeting(${JSON.stringify(id)})`);
    assert.equal(app.element('meeting-title').value, '合成项目');
    assert.match(app.run('transcriptText()'), /合成会议/);
    app.element('meeting-search').value = '不存在';
    await app.element('meeting-search').dispatch('input');
    assert.ok(!app.element('meeting-groups').innerHTML.includes('合成项目'));
    app.element('meeting-search').value = '合成项目';
    await app.element('meeting-search').dispatch('input');
    assert.match(app.element('meeting-groups').innerHTML, /合成项目/);
    await app.element('copy-transcript').click();
    assert.match(app.clipboard, /合成会议/);
    await app.element('clear-meeting-tags').click();
    await app.run('saveActiveMeeting()');
    assert.deepEqual(app.stores.get('meetings').get(id).tags, []);
    await app.run(`deleteMeetingRecord(${JSON.stringify(id)})`);
    assert.ok(!app.stores.get('meetings').has(id));
    assert.equal(harness().stores.size, 0);
  },
  async recording(state = 'recording', action = 'reset') {
    const app = meeting();
    await app.element('record-toggle').click();
    const socket = app.sockets[0];
    if (state !== 'connecting') await socket.open();
    const late = socket.onmessage;
    if (state !== 'connecting') {
      assert.equal(app.run('recorderState'), 'recording');
      app.run('audioProcessor.onaudioprocess({ inputBuffer: { getChannelData: () => new Float32Array([.1, -.1, .2, .3]) } })');
      assert.equal(socket.sent.at(-1).type, 'asr.stream.append');
      socket.message({ demo_event: 'asr.stream.result', result: { corrected_text: '新增转写。' } });
      assert.match(app.run('transcriptText()'), /新增转写/);
      await app.element('record-toggle').click();
      assert.equal(app.run('recorderState'), 'paused');
      assert.equal(socket.sent.at(-1).type, 'asr.stream.commit');
      if (state !== 'paused') {
        await app.element('record-toggle').click();
        assert.equal(app.run('recorderState'), 'recording');
      }
      if (state === 'finishing') {
        await app.element('finish-recording').click();
        assert.equal(socket.sent.at(-1).type, 'asr.stream.finish');
      }
    }
    const id = app.run('activeMeetingId');
    if (action === 'new') { await app.element('quick-new-meeting').click(); await app.settle(() => app.run('activeMeetingId') !== id); }
    else if (action === 'delete') await app.run(`deleteMeetingRecord(${JSON.stringify(id)})`);
    else await app.element('reset-recording').click();
    assert.ok(socket.closed);
    assert.ok(app.tracks.every(track => track.stopped));
    assert.ok(app.graphs.every(graph => graph.closed && graph.nodes.every(node => !node.connected || node.disconnected)));
    assert.equal(app.run('timerId'), null);
    assert.equal(app.run('finishFallbackTimer'), null);
    assert.equal(app.run('animationFrameId'), null);
    const text = app.run('transcriptText()');
    late({ data: JSON.stringify({ demo_event: 'asr.stream.result', result: { corrected_text: '过期结果' } }) });
    assert.equal(app.run('transcriptText()'), text);
  },
  async revision(mode = 'success', preset = '0', mutation) {
    const app = meeting(mutation);
    const complete = 'event: delta\ndata: ' + JSON.stringify({ text: '[[[CANVAS]]]新纪要[[[REPLY]]]已修改' }) + '\n\n';
    const events = mode === 'error' ? [complete, 'event: error\ndata: {"message":"offline failure"}\n\n', 'event: done\ndata: {}\n\n'] : mode === 'truncated' ? [complete] : [complete, 'event: done\ndata: {}\n\n'];
    app.respond = async () => sse(events);
    const buttons = app.document.querySelectorAll('[data-summary-prompt]');
    assert.equal(buttons.length, 4);
    await buttons[Number(preset)].click();
    await app.settle(() => !app.run('summaryRevisionRunning'));
    assert.equal(JSON.parse(app.requests[0].body).instruction, buttons[Number(preset)].dataset.summaryPrompt);
    assert.equal(app.element('summary-canvas').readOnly, false);
    assert.equal(app.element('summary-chat-send').disabled, false);
    if (mode === 'success') {
      assert.equal(app.run('summaryContent()'), '新纪要');
      assert.equal(app.run('summaryCustomized'), true);
      await app.element('undo-summary-revision').click();
      assert.equal(app.run('summaryContent()'), '原纪要');
      app.element('summary-canvas').value = '手工修改';
      await app.element('summary-canvas').dispatch('input');
      await app.element('copy-summary-canvas').click();
      await app.run('saveActiveMeeting()');
      assert.equal(app.clipboard, '手工修改');
      assert.equal(app.stores.get('meetings').get(app.run('activeMeetingId')).summary_content, '手工修改');
    } else {
      assert.equal(app.run('summaryContent()'), '原纪要', 'failed/truncated SSE must preserve original');
      assert.equal(app.run('summaryUndoStack.length'), 0);
    }
  },
  async lateRevision() {
    const app = meeting();
    const pending = deferred();
    app.respond = () => pending.promise;
    const work = app.run("reviseSummaryWithChat('精简')");
    app.run('resetSession({ persist: false })');
    const resetCanvas = app.element('summary-canvas').value;
    pending.resolve(sse(['event: delta\ndata: {"text":"[[[CANVAS]]]旧请求[[[REPLY]]]完成"}\n\n', 'event: done\ndata: {}\n\n']));
    await work;
    assert.equal(app.element('summary-canvas').value, resetCanvas, 'late stream must not repaint reset canvas');
  },
  async summary(mode = 'success') {
    const app = meeting();
    const pending = deferred();
    app.respond = () => pending.promise;
    const work = app.run('generateSummary({ explicit: true })');
    if (mode === 'late') app.run('resetSession({ persist: false })');
    pending.resolve(json(mode === 'empty' ? {content: ' '} : mode === 'failure' ? { detail: { message: 'offline failure' } } : { content: '新摘要' }, mode === 'failure' ? 502 : 200));
    await work;
    assert.equal(app.run('summaryContent()'), mode === 'late' ? '' : ['failure', 'empty'].includes(mode) ? '原纪要' : '新摘要');
    assert.equal(app.run('summaryRunning'), false);
    assert.equal(app.element('generate-summary').disabled, false);
  },
  async tts(mode = 'success', format = 'mp3', mutation) {
    const app = harness(mutation);
    app.run("systemTtsKeyConfigured = true; renderTtsVoices({tts: {default_voice: 'one', voices: [{id: 'one', label: 'One'}, {id: 'two', label: 'Two'}]}})");
    assert.equal(app.run('selectedTtsVoice'), 'one');
    const card = app.document.querySelectorAll('.voice-card').find(item => item.dataset.voice === 'two');
    await app.element('voice-options').dispatch('click', { target: card });
    const button = app.document.querySelectorAll('.format-button').find(item => item.dataset.format === format);
    await button.click();
    app.element('tts-text').value = mode === 'empty' ? '  ' : mode === 'long' ? '合成'.repeat(2000) : '合成';
    await app.element('tts-text').dispatch('input');
    app.respond = async () => {
      if (mode === 'timeout') throw new Error('offline timeout');
      if (mode === 'error') return json({ detail: 'offline failure' }, 502);
      return audio(mode === 'emptyAudio' ? '' : 'synthetic');
    };
    await app.element('synthesize-voice').click();
    assert.equal(app.run('ttsGenerating'), false);
    assert.equal(app.element('synthesize-voice').disabled, false);
    if (['error', 'timeout', 'emptyAudio'].includes(mode)) assert.equal(app.run('ttsAudioUrl'), null);
    else if (mode === 'empty') assert.equal(app.requests.length, 0);
    else {
      assert.deepEqual(JSON.parse(app.requests[0].body), { text: app.element('tts-text').value, voice: 'two', format });
      assert.equal(app.element('result-player').hidden, false);
      await app.element('download-voice').click();
      assert.ok(app.downloads.at(-1).download.endsWith(`.${format}`));
      assert.equal(app.downloads.at(-1).href, app.run('ttsAudioUrl'));
    }
    app.run("selectTtsVoice('clone'); renderTtsVoices({tts: {voices: [{id: 'new', label: 'New'}]}})");
    assert.equal(app.run('voiceSource'), 'clone');
    assert.ok(app.element('clone-voice-card').classList.contains('active'));
    app.run("selectTtsVoice('new'); systemTtsKeyConfigured = false; updateVoiceSubmitState()");
    assert.ok(app.element('synthesize-voice').disabled);
    assert.match(app.element('synthesize-voice').title, /配置/);
  },
  async token() {
    const app = harness();
    app.run("storageMode = 'account'; authUser = {id: 'offline'}; csrfToken = 'csrf'");
    app.respond = async (url, options) => options.method === 'POST' ? json({ token: 'cv_once', token_info: { id: 'token' } }) : json({ tokens: [] });
    await app.element('open-token-create').click();
    await app.element('create-api-token').click();
    assert.equal(app.element('api-token-output').textContent, 'cv_once');
    assert.equal(app.clipboard, 'cv_once');
    assert.equal(app.requests[0].headers['X-CSRF-Token'], 'csrf');
    await app.element('settings-dialog').dispatch('close');
    assert.equal(app.element('api-token-output').textContent, '');
    assert.ok(app.element('api-token-result').hidden);
    await app.element('open-token-create').click();
    assert.equal(app.element('api-token-output').textContent, '');
  },
  async navigation() {
    const app = meeting();
    for (const product of ['studio', 'conversation', 'meeting']) {
      await app.document.querySelectorAll('.product-tab').find(item => item.dataset.product === product).click();
      assert.equal(app.run('activeProductView'), product);
      assert.equal(app.document.querySelectorAll('[data-product-view]').find(item => item.dataset.productView === product).hidden, false);
    }
    app.run("updateRecorderUi('recording')");
    assert.equal(app.run("switchProductView('studio')"), false);
    assert.equal(app.run('activeProductView'), 'meeting');
    app.run("updateRecorderUi('idle')");
    for (const tab of app.document.querySelectorAll('.content-tab')) {
      await tab.click();
      assert.equal(app.run('activeTab'), tab.dataset.tab);
      assert.ok(tab.classList.contains('active'));
    }
    await app.element('toggle-settings-menu').dispatch('pointerdown');
    assert.equal(app.element('settings-menu').hidden, false);
    app.run('openSettingsDialog()');
    assert.equal(app.element('settings-dialog').open, true);
    const links = app.document.querySelectorAll('a').filter(item => item.target === '_blank');
    assert.ok(links.length >= 2);
    for (const link of links) {
      assert.ok(link.href && !link.href.startsWith('javascript:'));
      assert.match(link.rel, /noopener|noreferrer/);
    }
  },
};

async function main() {
  const [name, ...args] = process.argv.slice(2);
  if (name === 'mutations') {
    await assert.rejects(cases.revision('error', '0', ["if (eventName === 'error') throw new Error(eventPayload.message || '纪要修改失败');", '']), /preserve original/);
    await assert.rejects(cases.tts('success', 'wav', ["generatedAudioExtension = selectedTtsFormat;", "generatedAudioExtension = 'mp3';"]));
  } else {
    assert.ok(cases[name], `unknown case ${name}`);
    await cases[name](...args);
  }
  console.log(`PASS ${[name, ...args].join(' ')}`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
