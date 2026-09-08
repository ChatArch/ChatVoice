"""Opt-in real HTTP/SSE/WebSocket acceptance; no browser and no implicit retries.

Run from the source checkout with web/dev dependencies and ffmpeg installed.
The caller selects an HTTPS deployment and explicitly accepts bounded live usage.
No provider configuration is changed and no meeting/account records are created.
"""
import argparse
import asyncio
import base64
from collections import Counter
import inspect
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode, urlsplit
import wave

TRANSCRIPT = '今天讨论会议记录工具。小李负责接口配置，小王负责周五前完成测试。先修复纪要与语音，不更改其他服务。'
PRESETS = ('压缩成三点', '整理行动项', '正式纪要', '检查遗漏')


def checked_target(url):
    p = urlsplit(url)
    if (p.scheme != 'https' or not p.hostname or p.username is not None
            or p.password is not None or p.query or p.fragment or p.path not in ('', '/')
            or any(c.isspace() for c in url)):
        raise ValueError('Use one HTTPS service origin without credentials, path, query or fragment')
    p.port
    return url.rstrip('/')


def checked_revision(body):
    events = []
    for block in body.replace('\r\n', '\n').split('\n\n'):
        lines = block.splitlines()
        name = next((s[6:].strip() for s in lines if s.startswith('event:')), '')
        data = '\n'.join(s[5:].strip() for s in lines if s.startswith('data:'))
        if data:
            events.append((name, json.loads(data)))
    if any(name == 'error' for name, _ in events):
        raise ValueError('SSE error event (HTTP 200 is not success)')
    if not events or events[-1][0] != 'done':
        raise ValueError('Missing terminal SSE done event')
    text = ''.join(d.get('text', '') for name, d in events if name == 'delta')
    if '[[[CANVAS]]]' not in text or '[[[REPLY]]]' not in text:
        raise ValueError('Missing revision canvas/reply markers')
    canvas = text.split('[[[CANVAS]]]', 1)[1].split('[[[REPLY]]]', 1)[0].strip()
    if not canvas:
        raise ValueError('Empty revision canvas')
    return text


def read_ui_defaults(html):
    from html.parser import HTMLParser
    class Defaults(HTMLParser):
        def __init__(self):
            super().__init__(); self.in_voice=False; self.in_text=False; self.voice=''; self.text=[]
        def handle_starttag(self, tag, attrs):
            a=dict(attrs)
            if tag=='select': self.in_voice=a.get('id')=='conversation-voice'
            if tag=='textarea': self.in_text=a.get('id')=='tts-text'
            if tag=='option' and self.in_voice and (not self.voice or 'selected' in a): self.voice=a.get('value','')
        def handle_endtag(self, tag):
            if tag=='select': self.in_voice=False
            if tag=='textarea': self.in_text=False
        def handle_data(self, data):
            if self.in_text:self.text.append(data)
    parser=Defaults();parser.feed(html)
    text=''.join(parser.text).strip()
    require(parser.voice and text,'Deployed UI voice/default text contract missing')
    return {'voice':parser.voice,'text':text}


def result_exit_code(cases):
    return 0 if cases and all(c['status'] == 'pass' for c in cases) else 1


class ProviderFailure(ValueError):
    def __init__(self, code):
        known = {'AccessDenied.Unpurchased', 'InvalidApiKey', 'QuotaExceeded'}
        self.blocked = isinstance(code, str) and code in known
        self.code = code if self.blocked else 'UpstreamError'
        super().__init__(self.code)


def raise_provider_error(payload):
    if payload.get('demo_event') == 'proxy.error':
        raise ProviderFailure(payload.get('error_type'))
    if payload.get('type') == 'error':
        error = payload.get('error')
        raise ProviderFailure(error.get('code') if isinstance(error, dict) else None)
    if not payload.get('type') and payload.get('code'):
        raise ProviderFailure(payload.get('code'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decode_audio(path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', '-'],
                       capture_output=True, timeout=20)
    require(r.returncode == 0, 'Audio decode failed')
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)],
                       capture_output=True, text=True, timeout=10)
    require(r.returncode == 0, 'Audio duration inspection failed')
    duration = float(json.loads(r.stdout)['format']['duration'])
    require(duration > 0, 'Empty audio duration')
    return {'bytes': path.stat().st_size, 'duration_seconds': duration, 'decoded': True}


def ws_options(connect):
    # websockets 15 added environment proxy discovery. The tested server owns its
    # upstream routing; the verifier's unrelated shell proxy must not change it.
    return {'proxy': None} if 'proxy' in inspect.signature(connect).parameters else {}


async def realtime_exchange(origin, model, voice, out):
    import websockets
    url = origin.replace('https://', 'wss://', 1) + '/ws/realtime?' + urlencode({'model': model})
    event_types, text, audio, updated, submitted = [], [], bytearray(), False, False
    async with websockets.connect(url, open_timeout=15, close_timeout=3, max_size=8_000_000,
                                  **ws_options(websockets.connect)) as ws:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            payload = json.loads(await asyncio.wait_for(ws.recv(), max(.01, deadline-time.monotonic())))
            kind = payload.get('demo_event'); event_types.append(kind)
            raise_provider_error(payload)
            if kind == 'proxy.connected':
                await ws.send(json.dumps({'type': 'session.update', 'session': {
                    'modalities': ['text', 'audio'], 'voice': voice,
                    'instructions': '用简短中文回答，只说你好。', 'input_audio_format': 'pcm',
                    'output_audio_format': 'pcm', 'max_history_turns': 20,
                    'turn_detection': {'type': 'server_vad', 'threshold': .5, 'silence_duration_ms': 700}}}))
            elif kind == 'transcript.delta' and payload.get('role') == 'assistant':
                text.append(payload.get('text', ''))
            elif kind == 'audio.delta':
                audio.extend(base64.b64decode(payload['audio'], validate=True))
                require(len(audio) <= 8_000_000, 'Realtime audio cap exceeded')
            elif kind == 'upstream.event':
                event = payload.get('event', {}); event_types.append(event.get('type'))
                raise_provider_error(event)
                if event.get('type') == 'session.updated':
                    updated = True
                    if not submitted:
                        submitted = True
                        await ws.send(json.dumps({'type': 'conversation.item.create', 'item': {
                            'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': '请只说你好。'}]}}))
                        await ws.send(json.dumps({'type': 'response.create', 'response': {'modalities': ['audio', 'text']}}))
                if event.get('type') == 'response.done':
                    require(updated and submitted and any(t.strip() for t in text) and len(audio)>0,
                            'Realtime done without configured session, text and audio')
                    require(event.get('response', {}).get('status', 'completed') == 'completed', 'Realtime response not completed')
                    require(len(audio) % 2 == 0, 'Invalid PCM16 framing')
                    with wave.open(str(out / 'realtime.wav'), 'wb') as w:
                        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(audio)
                    return {**decode_audio(out/'realtime.wav'), 'event_types': event_types,
                            'text_chars': sum(map(len,text)), 'socket_context_closed_on_return': True}
        raise TimeoutError('Realtime response did not complete')


async def asr_exchange(origin, audio_path):
    import websockets
    with wave.open(str(audio_path), 'rb') as w:
        require((w.getnchannels(),w.getsampwidth(),w.getframerate()) == (1,2,16000), 'ASR fixture must be mono PCM16 16kHz')
        pcm = w.readframes(w.getnframes())
    results, commits, events = [], 0, []
    async with websockets.connect(origin.replace('https://','wss://',1)+'/ws/asr/stream',
                                  open_timeout=15,close_timeout=3,**ws_options(websockets.connect)) as ws:
        ready = json.loads(await asyncio.wait_for(ws.recv(),15))
        require(ready.get('demo_event')=='asr.stream.ready','ASR ready missing')
        await ws.send(json.dumps({'type':'asr.stream.start','sample_rate':16000,'chunk_seconds':4.0}))
        started=json.loads(await asyncio.wait_for(ws.recv(),15))
        require(started.get('demo_event')=='asr.stream.started','ASR started missing')
        # Each commit corresponds to a pause; append again corresponds to resume.
        for final in (False,True):
            for pos in range(0,len(pcm),16000): await ws.send(pcm[pos:pos+16000])
            await ws.send(json.dumps({'type':'asr.stream.finish' if final else 'asr.stream.commit'}))
            deadline=time.monotonic()+65
            while True:
                event=json.loads(await asyncio.wait_for(ws.recv(),max(.01,deadline-time.monotonic())))
                kind=event.get('demo_event');events.append(kind)
                require(kind!='asr.stream.error','ASR stream error')
                if kind=='asr.stream.result':
                    r=event.get('result',{});text=r.get('corrected_text') or r.get('raw_text') or ''
                    if text.strip(): results.append(text)
                if kind=='asr.stream.done':
                    require(event.get('final') is final,'Wrong commit/finish state');commits+=1;break
        require(results and commits==2,'ASR produced no transcript or missed a boundary')
    return {'commits':commits,'transcript_chars':sum(map(len,results)),'events':events,'socket_closed':True}


def checked_job_id(value):
    import re
    require(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',value),'Invalid clone job id')
    return value


def clone_exchange(client, reference, account, password, out):
    require(account.startswith('qa-verify-') and password,'Use a dedicated qa-verify- account, never a real user')
    require(reference.is_file() and 44 < reference.stat().st_size < 10_000_000,'Invalid synthetic reference file')
    job=None;headers={};terminal=False;authenticated=False;result={}
    def logged(event):
        (out/'clone-cleanup.json').write_text(json.dumps(event,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        r=client.post('/api/auth/login',json={'account':account,'password':password});r.raise_for_status()
        d=r.json();require(d.get('authenticated') is True,'Clone test login failed')
        authenticated=True;headers={'X-CSRF-Token':d['csrf_token']}
        require(client.get('/api/auth/session').json().get('authenticated') is True,'Login readback failed')
        with reference.open('rb') as f:
            r=client.post('/api/voice-clone/jobs',headers=headers,data={'text':'你好，这是自动回归生成。','lang':'zh','duration_factor':'1'},files={'reference_audio':('synthetic-reference.wav',f,'audio/wav')})
        r.raise_for_status();job=checked_job_id(r.json().get('job_id'));logged({'job_id':job,'owned_by_this_run':True,'cleanup':'pending'})
        deadline=time.monotonic()+240
        while time.monotonic()<deadline:
            r=client.get('/api/voice-clone/jobs/'+job);r.raise_for_status();state=r.json().get('status')
            if state in ('ready','failed'):
                terminal=True;require(state=='ready','Clone generation failed');break
            time.sleep(1)
        require(terminal,'Clone deadline exceeded; running job retained for safe operator follow-up')
        r=client.get('/api/voice-clone/jobs/'+job+'/audio');r.raise_for_status()
        path=out/'clone.wav';path.write_bytes(r.content);result=decode_audio(path)
    finally:
        try:
            if job and terminal:
                r=client.delete('/api/voice-clone/jobs/'+job,headers=headers);r.raise_for_status()
                require(client.get('/api/voice-clone/jobs/'+job).status_code==404,'Clone cleanup readback failed')
                logged({'job_id':job,'owned_by_this_run':True,'cleanup':'verified-404'});result['job_deleted']=True
        finally:
            if authenticated:
                r=client.post('/api/auth/logout',headers=headers);r.raise_for_status()
                require(client.get('/api/auth/session').json().get('authenticated') is False,'Logout readback failed')
                result['session_revoked']=True
    return result


def run(origin, out, *, include_realtime=False, audio=None, clone=None):
    import httpx
    out.mkdir(parents=True,exist_ok=True)
    receipt={'origin':origin,'browser_used':False,'real_provider_calls':True,'cases':[],
             'exclusions':['pixel layout / physical microphone / OS clipboard','account/meeting mutations (offline suite covers logic)'],
             'selected_optional_flows':{'asr':bool(audio),'realtime':include_realtime,'clone':bool(clone)}}
    def save():
        receipt['counts']=dict(Counter(c['status'] for c in receipt['cases']))
        (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    def case(name,fn):
        start=time.monotonic();r={'id':name}
        try:r.update(status='pass',evidence=fn())
        except ProviderFailure as e:
            r.update(status='blocked' if e.blocked else 'fail',error_code=e.code)
        except Exception as e:
            # No arbitrary exception text: upstream data may include secrets.
            r.update(status='fail',error_type=type(e).__name__)
            if isinstance(e,httpx.HTTPStatusError):r['http']=e.response.status_code
        r['seconds']=round(time.monotonic()-start,3);receipt['cases'].append(r);save()
        print(json.dumps(r,ensure_ascii=False),flush=True)
        return r.get('evidence')
    with httpx.Client(base_url=origin,timeout=90,trust_env=False,follow_redirects=False) as client:
        def get_status():
            r=client.get('/api/status');r.raise_for_status();d=r.json()
            require(isinstance(d.get('tts'),dict),'TTS status missing');return d
        status=case('status',get_status)
        if status is None:
            receipt['cases'].append({'id':'generation-flows','status':'blocked','reason':'status unavailable'});save();return receipt
        def defaults():
            r=client.get('/');r.raise_for_status();return read_ui_defaults(r.text)
        ui=case('deployed-ui-contract',defaults)
        def post(path,payload):
            r=client.post(path,json=payload);r.raise_for_status();return r
        def notes():
            d=post('/api/meeting-notes/polish',{'transcript':TRANSCRIPT,'instruction':'简短列出结论和行动项。'}).json()
            require(isinstance(d.get('content'),str) and d['content'].strip(),'Empty notes');return d
        summary=case('notes-generate',notes)
        def title():
            d=post('/api/meeting-title',{'transcript':TRANSCRIPT}).json()
            require(isinstance(d.get('title'),str) and d['title'].strip(),'Empty title');return d
        case('title-generate',title)
        for instruction in PRESETS:
            if summary is None:
                receipt['cases'].append({'id':'revision-'+instruction,'status':'blocked','reason':'notes failed'});save();continue
            def revise(instruction=instruction):
                r=post('/api/meeting-notes/revise/stream',{'transcript':TRANSCRIPT,'current_summary':summary['content'],'instruction':instruction})
                text=checked_revision(r.text);return {'http':r.status_code,'stream_complete':True,'chars':len(text)}
            case('revision-'+instruction,revise)
        voices=status['tts'].get('voices',[])
        if not voices:
            receipt['cases'].append({'id':'tts-voices','status':'blocked','reason':'no configured voices'});save()
        for i,voice in enumerate(voices):
            for fmt in ('mp3','wav'):
                def tts(i=i,voice=voice,fmt=fmt):
                    r=post('/api/tts',{'text':'你好，这是完整操作流程的自动测试。','voice':voice['id'],'format':fmt})
                    require(r.headers.get('content-type','').startswith('audio/'),'Not an audio response')
                    path=out/f'tts-{i}.{fmt}';path.write_bytes(r.content);return decode_audio(path)
                case(f'tts-{i}-{fmt}',tts)
        if voices and ui:
            def default_tts():
                r=post('/api/tts',{'text':ui['text'],'voice':voices[0]['id'],'format':'mp3'})
                require(r.headers.get('content-type','').startswith('audio/'),'Not audio')
                path=out/'tts-default.mp3';path.write_bytes(r.content)
                return {**decode_audio(path),'input_chars':len(ui['text'])}
            case('tts-untouched-ui-text',default_tts)
        def empty():
            r=client.post('/api/tts',json={'text':'','format':'mp3'})
            require(r.status_code in (400,422),'Empty TTS input accepted');return {'http':r.status_code}
        case('tts-empty-rejected',empty)
        if audio:case('asr-pause-resume-finish',lambda:asyncio.run(asr_exchange(origin,audio)))
        if clone:case('clone-generate-download-delete-logout',lambda:clone_exchange(client,*clone,out))
        if include_realtime:
            if status.get('token_plan_key') is not True or not ui:
                receipt['cases'].append({'id':'realtime-configure-send-receive-close','status':'blocked','reason':'Token Plan/UI prerequisites missing'});save()
            else:
                case('realtime-configure-send-receive-close',lambda:asyncio.run(realtime_exchange(origin,status['realtime_model'],ui['voice'],out)))
    save();return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live',action='store_true',help='Explicitly allow synthetic real provider calls; may consume configured Plan quota.')
    p.add_argument('--url',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--realtime',action='store_true');p.add_argument('--asr-audio',type=Path)
    p.add_argument('--clone-reference',type=Path,help='Synthetic reference; requires a pre-provisioned qa-verify- account.')
    p.add_argument('--account-env',default='CHATVOICE_VERIFY_ACCOUNT')
    p.add_argument('--password-env',default='CHATVOICE_VERIFY_PASSWORD')
    args=p.parse_args(argv)
    if not args.live:p.error('No network without explicit --live opt-in')
    try:origin=checked_target(args.url)
    except ValueError:p.error('Invalid service origin; HTTPS without credentials required')
    if args.asr_audio and not args.asr_audio.is_file():p.error('ASR fixture does not exist')
    clone=None
    if args.clone_reference:
        import os
        account=os.environ.get(args.account_env,'');password=os.environ.get(args.password_env,'')
        if not account.startswith('qa-verify-') or not password or not args.clone_reference.is_file():
            p.error('Clone requires a synthetic file and qa-verify- account/password from named environment variables')
        clone=(args.clone_reference,account,password)
    receipt=run(origin,args.out,include_realtime=args.realtime,audio=args.asr_audio,clone=clone)
    return result_exit_code(receipt['cases'])


if __name__=='__main__':
    raise SystemExit(main())
