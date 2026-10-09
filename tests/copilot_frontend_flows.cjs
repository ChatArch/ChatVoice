// Execute the shipped controller; fake only transport, clock and Web Audio.
const {harness, json, sse, deferred, assert} = require('./nonbrowser_harness.cjs');
const reply = () => sse(['event: delta\ndata: {"text":"旧回复"}\n\n', 'event: done\ndata: {"completion_marker":"copilot.answer.done"}\n\n']);
const materials = (name, revision) => ({materials:[{id:name,filename:`${name}.txt`,preview:name}],material_revision:revision});
function setup() {
  const app = harness();
  app.run("storageMode='account'; authUser={id:'offline'}; csrfToken='csrf'; copilotEnabled=true; copilotAutoPrepare=true;");
  app.element('copilot-question').value = '支持吗？';
  app.respond = async url => {
    if (url === '/api/auth/session') return json({authenticated:true,user:{id:'offline'},csrf_token:'csrf'});
    if (url === '/api/copilot/status') return json({enabled:true,auto_prepare:true});
    return json({materials:[],meetings:[],conversations:[],material_revision:1});
  };
  return app;
}
module.exports = {
  async copilotDirect() {
    const app = setup(); app.context.location.pathname='/copilot';
    await app.run('bootstrapAccess()');
    assert.equal(app.run('activeProductView'),'copilot');
    assert.equal(app.element('copilot-shell').hidden,false);
    const moves=[]; app.context.location.assign=url=>moves.push(url);
    await app.run('openSharedLogin()'); assert.deepEqual(moves,['/login?next=%2Fcopilot']);
    app.element('copilot-material-file').files=[new Blob(['synthetic material'])];
    await app.element('copilot-upload').click();
    assert.ok(app.requests.some(r=>r.url==='/api/copilot/materials' && r.method==='POST'));
    await app.element('copilot-start-mic').click(); await app.sockets[0].open();
    app.sockets[0].message({demo_event:'asr.stream.result',result:{text:'支持吗？',stream:{revision:1}}});
    app.respond=async()=>reply(); await app.element('copilot-submit').click();
    assert.equal(app.element('copilot-answer').textContent,'旧回复');
    app.run('stopCopilotAudio()');
  },
  async copilotGraph(mode='mix') {
    const app=setup(), sources=[], gains=[];
    const Base=app.context.AudioContext;
    app.context.AudioContext=class extends Base {
      node() {const n=super.node();n.edges=[];n.connect=function(to){this.edges.push(to);};return n;}
      createMediaStreamSource(stream){const n=this.node();n.stream=stream;sources.push(n);return n;}
      createGain(){const n=this.node();n.gain={value:1};gains.push(n);return n;}
    };
    const tabTrack={stop(){this.stopped=true;}}; app.tracks.push(tabTrack);
    if(mode!=='unsupported') app.context.navigator.mediaDevices.getDisplayMedia=async()=>({getTracks:()=>[tabTrack],getAudioTracks:()=>[tabTrack]});
    else app.tracks.pop();
    await app.element('copilot-start-tab').click();
    if(mode==='unsupported'){assert.equal(app.run('copilotAudioState'),'error');assert.ok(app.tracks.every(t=>t.stopped));return;}
    assert.equal(sources.length,2,'mic and tab must both enter audio graph');
    const processor=app.run('copilotAudioProcessor');
    function weight(n,seen=new Set()){if(n===processor)return 1;if(seen.has(n))return 0;seen.add(n);return (n.gain?.value??1)*n.edges.reduce((s,e)=>s+weight(e,new Set(seen)),0);}
    assert.ok(sources.every(n=>weight(n)>0),'both streams reach PCM processor');
    assert.ok(sources.reduce((s,n)=>s+weight(n),0)<=1,'mix has headroom');
    await app.sockets[0].open();
    const value=weight(sources[1])*.8; // silent mic, audible tab
    processor.onaudioprocess({inputBuffer:{getChannelData:()=>new Float32Array(12).fill(value)}});
    assert.ok(Buffer.from(app.sockets[0].sent.at(-1).audio,'base64').readInt16LE(0)>0,'tab contributes sent PCM');
    await app.element('copilot-stop-audio').click();
    assert.ok([...sources,...gains].every(n=>n.disconnected));assert.ok(app.tracks.every(t=>t.stopped));assert.ok(app.graphs.every(g=>g.closed));
  },
  async copilotSafety(kind='draft',action='question') {
    const app=setup(), pending=deferred(), logoutPending=deferred();
    app.respond=async (url,options={})=>{
      if(url==='/api/copilot/answer/stream'||url==='/api/copilot/prepare')return pending.promise;
      if(url==='/api/copilot/materials'&&options.method==='POST')return json({material_revision:2});
      if(url==='/api/copilot/materials')return json(materials('current',2));
      if(url==='/api/auth/logout')return logoutPending.promise;
      return json({meetings:[],conversations:[]});
    };
    if(kind==='manual'||action==='logout') app.run("globalThis.copilotRenderCount=0;const originalCopilotRender=renderCopilotTranscript;renderCopilotTranscript=function(){globalThis.copilotRenderCount++;return originalCopilotRender();};");
    const work=app.run(kind==='draft'?'prepareCopilotDraft()':'submitCopilotAnswer()');
    await app.settle(()=>app.requests.length>0);
    const field={question:'copilot-question',instructions:'copilot-instructions',style:'copilot-style'}[action];
    if(field){app.element(field).value='更改内容';await app.element(field).dispatch('input');}
    else if(action==='material'){app.element('copilot-material-file').files=[new Blob(['material'])];await app.element('copilot-upload').click();}
    else if(action==='transcript'||action==='denial'||action==='continued') app.run(`copilotTranscriptState.applyResult({text:${JSON.stringify(action==='denial'?'不是这个问题。':'继续说明新条件。')},stream:{revision:2}})`);
    else if(action==='stop') await app.element('copilot-stop-audio').click();
    else if(action==='pause') await app.element('copilot-pause-audio').click();
    else if(action==='reset') await app.element('reset-recording').click();
    else if(action==='logout') {
      const logoutWork=app.element('account-action').click();
      await app.settle(()=>app.requests.some(request=>request.url==='/api/auth/logout'));
      const rendered=app.run('copilotRenderCount');
      logoutPending.resolve(json({authenticated:false}));await logoutWork;
      assert.ok(rendered>0,'logout invalidation must render before its response');
    }
    if(action!=='logout') logoutPending.resolve(json({authenticated:false}));
    if(kind==='manual'&&['instructions','style','material','stop','reset','logout'].includes(action)) {
      assert.ok(app.run('copilotRenderCount')>0,`${action} invalidation must render immediately`);
      assert.equal(app.element('copilot-submit').disabled,['reset','logout'].includes(action));
    }
    pending.resolve(reply());await work;
    assert.doesNotMatch(app.element('copilot-answer').textContent,/旧回复/);
    assert.doesNotMatch(app.element('copilot-prepared-answer').textContent,/旧回复/);
    assert.equal(app.run('copilotLastCompletionMarker'),'');
  },
  async copilotDedupe() {
    const app=setup(), pending=deferred();app.respond=()=>pending.promise;
    const work=app.run('prepareCopilotDraft()');
    await app.run('prepareCopilotDraft()');
    const manual=app.element('copilot-submit').click();
    assert.equal(app.requests.length,1,'manual joins the exact pending prepare');
    pending.resolve(reply());await work;await manual;
    assert.equal(app.element('copilot-answer').textContent,'旧回复');
    await app.run('prepareCopilotDraft()');assert.equal(app.requests.length,1,'ready key is not prepared twice');
    app.element('copilot-question').value='另一个？';await app.element('copilot-question').dispatch('input');
    await app.run('prepareCopilotDraft()');assert.equal(app.requests.length,1,'cooldown enforced by controller');
    app.run('copilotPrepareCooldownUntil=0');await app.run('prepareCopilotDraft()');assert.equal(app.requests.length,2);
  },
  async copilotMaterialSafety(mode='lateList') {
    const app=setup();
    app.run("copilotMaterialRevision=7;renderCopilotMaterials([{id:'baseline',filename:'baseline.txt',preview:'baseline'}]);");
    if(mode==='repeatList') {
      const first=deferred(),second=deferred();let calls=0;
      app.respond=async url=>url==='/api/copilot/materials'?(++calls===1?first.promise:second.promise):json({meetings:[],conversations:[]});
      const firstWork=app.run('loadCopilotMaterials()');await app.settle(()=>app.requests.length===1);
      const secondWork=app.run('loadCopilotMaterials()');await app.settle(()=>app.requests.length===2);
      second.resolve(json(materials('newest',20)));await secondWork;
      first.resolve(json(materials('stale',99)));await firstWork;
      assert.equal(app.run('copilotMaterialRevision'),20,'older list must not replace the newest revision');
      assert.match(app.element('copilot-material-list').innerHTML,/newest\.txt/);
      assert.doesNotMatch(app.element('copilot-material-list').innerHTML,/stale\.txt/);
      assert.equal(app.requests[0].signal.aborted,true,'duplicate list aborts its predecessor');
      assert.equal(app.run('copilotMaterialListAbortController'),null);
      return;
    }
    const pending=deferred();
    app.respond=async (url,options={})=>{
      if(mode==='lateList'&&url==='/api/copilot/materials'&&!options.method)return pending.promise;
      if(mode==='lateUpload'&&url==='/api/copilot/materials'&&options.method==='POST')return pending.promise;
      if(mode==='lateDelete'&&url==='/api/copilot/materials/old'&&options.method==='DELETE')return pending.promise;
      if(url==='/api/copilot/materials')return json(materials('unexpected-refresh',88));
      if(url==='/api/auth/logout')return json({authenticated:false});
      return json({meetings:[],conversations:[]});
    };
    let work;
    if(mode==='lateList') work=app.run('loadCopilotMaterials()');
    else if(mode==='lateUpload') {
      app.element('copilot-material-file').files=[new Blob(['late upload'])];
      app.element('copilot-material-file').value='late.txt';
      work=app.element('copilot-upload').click();
    } else work=app.run("deleteCopilotMaterial('old')");
    await app.settle(()=>app.requests.length===1);
    const request=app.requests[0];
    if(mode==='lateList') await app.element('account-action').click();
    else if(mode==='lateUpload') app.run('resetSession({persist:false})');
    else {
      await app.run("activateStorageMode('account',{id:'second'},'csrf-2')");
      app.run("copilotMaterialRevision=11;renderCopilotMaterials([{id:'second',filename:'second.txt',preview:'second'}]);");
    }
    const expected={
      revision:app.run('copilotMaterialRevision'),
      html:app.element('copilot-material-list').innerHTML,
      workRevision:app.run('copilotWorkRevision'),
      refreshes:app.requests.filter(item=>item.url==='/api/copilot/materials'&&!item.method).length,
    };
    pending.resolve(json(mode==='lateList'?materials('late-list',99):{material_revision:99}));await work;
    assert.equal(app.run('copilotMaterialRevision'),expected.revision,'late material response must not change revision');
    assert.equal(app.element('copilot-material-list').innerHTML,expected.html,'late material response must not repaint UI');
    assert.equal(app.run('copilotWorkRevision'),expected.workRevision,'late mutation must not invalidate or prepare new work');
    assert.equal(app.requests.filter(item=>item.url==='/api/copilot/materials'&&!item.method).length,expected.refreshes,'late mutation must not refresh materials');
    assert.equal(app.requests.some(item=>item.url==='/api/copilot/prepare'),false);
    assert.equal(request.signal.aborted,true,'session invalidation aborts the material request');
    assert.equal(app.run('copilotMaterialListAbortController'),null);
    assert.equal(app.run('copilotMaterialMutationAbortController'),null);
    if(mode==='lateUpload')assert.equal(app.element('copilot-material-file').value,'late.txt','late upload must not clear the current selection');
    if(mode==='lateDelete')assert.equal(app.run('authUser.id'),'second');
  },
};
