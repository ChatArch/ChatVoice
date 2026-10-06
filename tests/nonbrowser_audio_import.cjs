const {harness, json, deferred, assert} = require('./nonbrowser_harness.cjs');
const mode = process.argv[2];
const file = new Blob(['RIFF-fixture-WAVE-audio'], {type: 'audio/wav'});
file.name = '会议.wav';
let finished = false;
const guard = setTimeout(() => { if (!finished) { console.error('Audio import case did not complete'); process.exitCode = 1; } }, 10000);

async function main() {
  const app = harness();
  const guest = mode.startsWith('guest');
  const transcript = mode === 'guest-long' ? '较长文字'.repeat(1600) : '文件转写测试内容';
  app.run(`storageMode = ${JSON.stringify(guest ? 'guest' : 'account')}; authUser = ${guest ? 'null' : "{id: 'offline'}"}; csrfToken = 'csrf'; setAudioRetentionMode('discard', {persist:false,announce:false});`);
  app.element('asr-channel').value = 'stub-local';
  if (mode === 'retained') app.run("setAudioRetentionMode('retain', {persist:false,announce:false})");
  const pending = deferred();
  let imported;
  let cancelCount = 0;
  app.respond = async (url, options = {}) => {
    if (url === '/api/heartbeat') return json({ok: true});
    if (url === '/api/meeting-title') return json({title:'导入会议标题'});
    if (url === '/api/meeting-notes/polish') return json({content:'导入会议摘要'});
    if (options.method === 'DELETE' && url.startsWith('/api/meeting-imports/')) { cancelCount++; return json({cancelled:true}); }
    if (options.method === 'PUT' && url.startsWith('/api/meetings/')) {
      const record = JSON.parse(options.body); imported = {id:url.split('/').at(-1), ...record, audio_assets:imported?.audio_assets || []}; return json(imported);
    }
    if ((!options.method || options.method === 'GET') && url.startsWith('/api/meetings/')) return mode === 'open-error' ? json({detail:'读取暂不可用'},503) : json(imported);
    if (options.method === 'POST' && url.endsWith('/import')) {
      assert.equal(options.headers['X-CSRF-Token'],'csrf');
      assert.equal(options.body.get('channel'),'stub-local');
      assert.equal(options.body.get('retain_audio'),String(mode === 'retained'));
      const id = url.split('/').at(-2);
      imported = {id, title:'会议', created_at:'2026-10-06T00:00:00Z', updated_at:'2026-10-06T00:00:00Z', duration_seconds:2, transcript_segments:[{speaker:'说话人 1',time:'00:00',text:'文件转写测试内容'}], summary_content:'', audio_retention:mode === 'retained', audio_assets:mode === 'retained' ? [{id:'audio_import_01',source:'import'}] : []};
      if (['cancel','new'].includes(mode)) return pending.promise;
      if (mode === 'failure') return json({detail:'识别失败，没有建立会议'},502);
      return json({meeting:imported},201);
    }
    if (url === '/api/asr') return json({corrected_text:transcript,engine:'provider-fixture'});
    throw new Error(`Unexpected ${options.method || 'GET'} ${url}`);
  };
  if (mode === 'empty') {
    const empty = new Blob([], {type:'audio/wav'}); empty.name = 'empty.wav'; app.element('meeting-import-file').files = [empty];
  } else {
    if (mode === 'oversize') Object.defineProperty(file,'size',{value:129*1024*1024});
    app.element('meeting-import-file').files = [file];
  }
  const original = app.run('activeMeetingId');
  const operation = app.element('meeting-import-file').dispatch('change');
  if (['cancel','new'].includes(mode)) {
    await app.settle(() => app.requests.some(r => r.method === 'POST' && r.url.endsWith('/import')));
    assert.equal(app.element('cancel-meeting-import').hidden,false);
    assert.equal(app.element('record-toggle').disabled,true);
    const lateRecord = structuredClone(imported);
    if (mode === 'cancel') await app.element('cancel-meeting-import').click();
    else await app.element('quick-new-meeting').click();
    const after = app.run('activeMeetingId');
    pending.resolve(json({meeting:lateRecord},201));
    await operation;
    assert.equal(cancelCount,1);
    assert.equal(app.run('activeMeetingId'),after,'late import cannot switch to another meeting');
    assert.equal(app.run('meetingImportRunning'),false);
    assert.ok(!app.requests.some(r => r.url === '/api/meeting-notes/polish'));
    return;
  }
  await operation;
  assert.equal(app.run('meetingImportRunning'),false);
  if (mode === 'open-error') {
    assert.match(app.element('meeting-import-status').textContent,/已完成.*无法打开|读取/);
    assert.equal(cancelCount,0,'successful import must not be deleted just because opening failed');
    assert.ok(!app.requests.some(r => r.url === '/api/meeting-notes/polish'));
    return;
  }
  if (['empty','oversize','failure'].includes(mode)) {
    assert.equal(app.run('activeMeetingId'),original);
    assert.match(app.element('meeting-import-status').textContent,/空|128 MiB|识别失败/);
    if (mode !== 'failure') assert.equal(app.requests.length,0);
    return;
  }
  assert.equal(app.run("transcriptSegments.map(s=>s.text).join('')"),transcript);
  assert.ok(app.run("transcriptSegments.every(s=>Array.from(s.text).length<=5000)"));
  assert.equal(app.run('showingDemo'),false);
  await app.settle(() => app.requests.some(r => r.url === '/api/meeting-notes/polish') && !app.run('summaryRunning'));
  assert.equal(app.run('summaryContent()'),'导入会议摘要');
  assert.equal(app.element('cancel-meeting-import').hidden,true);
  if (guest) assert.equal(app.stores.get('meetings').size,1);
  if (mode === 'retained') assert.match(app.element('meeting-audio-assets').innerHTML,/audio_import_01/);
}
main().then(() => { finished=true; clearTimeout(guard); console.log('PASS audio-import ' + mode); }, error => { finished=true;clearTimeout(guard);console.error(error);process.exitCode=1; });
