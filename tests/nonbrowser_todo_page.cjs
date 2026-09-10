const {harness, json, deferred, assert} = require('./nonbrowser_harness.cjs');
const mode=process.argv[2];
const guard=setTimeout(()=>{console.error('incomplete Todo case');process.exitCode=1;},10000);
function setup() {
  const h=harness();
  assert.equal(h.run('typeof generateTodoFromSummary'),'function','Markdown Todo controller must exist');
  h.run("storageMode='guest'; activeMeetingId='meeting-a'; activeMeetingCreatedAt='2026-09-11T00:00:00Z'; showingDemo=false; hasGeneratedSummary=true; recorderState='ended'; syncSummaryContent('先整理测试报告，再邀请评审。')");
  return h;
}
const markdown='# 执行计划\n\n- [ ] 整理测试报告\n- [ ] 邀请评审';
async function main() {
  const h=setup();
  if (mode==='empty') {
    assert.equal(h.run('todoContent()'),''); assert.equal(h.requests.length,0);
    h.run("setActiveTab('todo')"); assert.equal(h.requests.length,0);
  } else if (mode==='convert') {
    h.respond=async (url,opts)=>{assert.equal(url,'/api/meeting-notes/todo');assert.equal(JSON.parse(opts.body).summary,'先整理测试报告，再邀请评审。');return json({content:markdown,model:'offline'});};
    await h.element('summary-to-todo').click();
    assert.equal(h.run('activeTab'),'todo');assert.equal(h.run('todoContent()'),markdown);
    assert.equal(h.run('summaryContent()'),'先整理测试报告，再邀请评审。');
    await h.run('saveActiveMeeting()');const saved=await h.run('getStoredMeeting(activeMeetingId)');assert.equal(saved.todo_markdown,markdown);
  } else if (mode==='noAuto') {
    h.run("transcriptSegments=[{speaker:'说话人1',time:'00:01',text:'整理测试报告',demo:false}]");
    h.respond=async url=>{assert.equal(url,'/api/meeting-notes/polish');return json({content:'新摘要'});};
    await h.run('generateSummary({explicit:true})');assert.equal(h.run('todoContent()'),'');assert.equal(h.requests.length,1);
  } else if (mode==='revise') {
    h.element('todo-canvas').value=markdown;
    h.respond=async (url,opts)=>{assert.equal(url,'/api/meeting-notes/todo/revise');const body=JSON.parse(opts.body);assert.equal(body.current_todo,markdown);assert.equal(body.instruction,'拆解第一步');return json({content:markdown+'\n  - [ ] 汇总复现结果',reply:'已拆解第一步。'});};
    h.element('todo-chat-input').value='拆解第一步';await h.element('todo-chat-form').dispatch('submit');
    assert.match(h.run('todoContent()'),/汇总复现结果/);assert.equal(h.run('todoChatMessages.length'),2);
    await h.element('undo-todo').click();assert.equal(h.run('todoContent()'),markdown);
  } else if (mode==='failure'||mode==='invalid') {
    h.element('todo-canvas').value=markdown;
    h.respond=async()=>mode==='failure'?json({detail:'失败'},502):json({content:' '});
    await h.run("reviseTodoWithChat('精简')");assert.equal(h.run('todoContent()'),markdown);assert.equal(h.run('todoRunning'),false);assert.match(h.element('todo-status').textContent,/失败/);
  } else if (mode==='late'||mode==='edited'||mode==='cancel') {
    const p=deferred();h.respond=()=>p.promise;const work=h.run('generateTodoFromSummary()');
    if(mode==='late') h.run("resetSession({persist:false});activeMeetingId='meeting-b'");
    if(mode==='edited'){h.element('todo-canvas').value='- [x] 手工完成';await h.element('todo-canvas').dispatch('input');}
    if(mode==='cancel') await h.element('cancel-todo').click();
    p.resolve(json({content:markdown}));await work;
    assert.equal(h.run('todoContent()'),mode==='edited'?'- [x] 手工完成':'');
  } else if (mode==='existing') {
    h.element('todo-canvas').value='- [x] 保留';h.context.confirm=()=>false;
    await h.element('summary-to-todo').click();assert.equal(h.requests.length,0);assert.equal(h.run('todoContent()'),'- [x] 保留');
  } else if (mode==='persist') {
    h.element('todo-canvas').value=markdown;await h.element('todo-canvas').dispatch('input');await h.run('saveActiveMeeting()');
    await h.run('createNewMeeting({announce:false})');assert.equal(h.run('todoContent()'),'');
    await h.run("openMeeting('meeting-a')");assert.equal(h.run('todoContent()'),markdown);
    await h.element('copy-todo').click();assert.equal(h.clipboard,markdown);
    await h.element('download-todo').click();assert.ok(h.downloads[0].download.endsWith('.md'));
  } else if (mode==='noSummary') {
    h.run('hasGeneratedSummary=false');await h.element('summary-to-todo').click();assert.equal(h.requests.length,0);assert.match(h.element('todo-status').textContent,/先.*摘要/);
  } else if (mode==='duplicate') {
    const p=deferred();h.respond=()=>p.promise;const work=h.element('summary-to-todo').click();await h.element('summary-to-todo').click();assert.equal(h.requests.length,1);p.resolve(json({content:markdown}));await work;
  } else if (mode==='legacy') {
    await h.run("putStoredMeeting('legacy',{title:'旧会议',created_at:'2026-09-11T00:00:00Z',updated_at:'2026-09-11T00:00:00Z',transcript_segments:[],summary_content:'旧摘要'})");
    h.element('todo-canvas').value=markdown;await h.run("openMeeting('legacy')");assert.equal(h.run('todoContent()'),'');
  } else throw new Error('Unknown mode '+mode);
  console.log('PASS todo-page '+mode);
}
main().then(()=>clearTimeout(guard),e=>{clearTimeout(guard);console.error(e);process.exitCode=1;});
