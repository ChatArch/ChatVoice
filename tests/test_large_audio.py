import io
from pathlib import Path
import wave

import pytest

from test_meeting_audio_storage import audio_app


def padded_wav(size=13*1024*1024):
    stream=io.BytesIO()
    with wave.open(stream,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\0\0'*16000)
    data=stream.getvalue()
    # Valid RIFF JUNK extension makes a small-duration audio file exceed the former cap.
    padding=size-len(data)-8
    body=data+b'JUNK'+padding.to_bytes(4,'little')+b'\0'*padding
    return body[:4]+(len(body)-8).to_bytes(4,'little')+body[8:]


def test_large_limit_and_import_timeout_are_consistent(audio_app):
    assert audio_app.MAX_IMPORTED_AUDIO_BYTES == 128*1024*1024
    assert audio_app.MEETING_IMPORT_TIMEOUT_SECONDS >= 900


def test_dispatcher_accepts_over_12m_via_bounded_chunks(audio_app,monkeypatch,tmp_path):
    assert hasattr(audio_app,'_transcribe_large_audio'), 'large file chunk dispatch required'
    calls=[]
    def chunks(channel,data,filename,correct=True):
        calls.append((channel,len(data)))
        return {'corrected_text':'large fixture','raw_text':'large fixture','meta':{'chunks':1}}
    monkeypatch.setattr(audio_app,'_transcribe_large_audio',chunks)
    result=audio_app.transcribe_audio_bytes('funasr-gpu',padded_wav(),'large.wav')
    assert result['corrected_text']=='large fixture'
    assert calls==[('funasr-gpu',13*1024*1024)]


def test_real_large_upload_import_uses_small_provider_windows(audio_app,monkeypatch):
    import asyncio,httpx
    sizes=[]
    def provider(data,filename):
        sizes.append(len(data))
        return audio_app.normalize_asr_result('funasr-gpu','large route fixture','large route fixture',{'engine':'provider-fixture'})
    monkeypatch.setattr(audio_app,'_funasr_gpu_asr',provider)
    async def flow():
        from test_meeting_audio_storage import _login
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app),base_url='https://app.example.test') as client:
            csrf=await _login(client,audio_app,'large-route@example.test')
            result=await client.post('/api/meetings/large-route/import',headers=csrf,data={'import_token':'large-route-token','channel':'funasr-gpu'},files={'file':('large.wav',padded_wav(),'audio/wav')})
            assert result.status_code==201,result.text
            assert result.json()['meeting']['transcript_segments'][0]['text']=='large route fixture'
            assert sizes and max(sizes)<=12*1024*1024
            assert not list(Path(audio_app.AUDIO_UPLOAD_TEMP_DIR).glob('*'))
    asyncio.run(asyncio.wait_for(flow(),15))


def test_ffmpeg_splits_audio_into_bounded_windows(tmp_path):
    from chatvoice import asr_chunks
    source=tmp_path/'source.wav'
    with wave.open(str(source),'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\0\0'*16000*65)
    sizes=[]
    def provider(data,index):
        with wave.open(io.BytesIO(data),'rb') as decoded:
            frames=decoded.getnframes();assert frames<=16000*30
        sizes.append(len(data));return {'raw_text':f'window {index}','corrected_text':f'window {index}'}
    result=asr_chunks.transcribe_file(source,provider)
    assert len(sizes)==3
    assert result['corrected_text']=='window 1\nwindow 2\nwindow 3'
    assert result['chunks']==3


def test_chunk_provider_failure_is_not_partial_success(tmp_path):
    from chatvoice import asr_chunks
    source=tmp_path/'source.wav'
    with wave.open(str(source),'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\0\0'*16000*35)
    def provider(data,index):
        if index==2:raise RuntimeError('provider failure')
        return {'corrected_text':'partial'}
    with pytest.raises(RuntimeError,match='provider failure'):
        asr_chunks.transcribe_file(source,provider)


def test_cancel_before_decode_has_no_provider_call(tmp_path):
    from chatvoice import asr_chunks
    with pytest.raises(asr_chunks.AudioProcessingCancelled):
        asr_chunks.transcribe_file(tmp_path/'unused.wav',lambda *a:pytest.fail('provider must not run'),cancelled=lambda:True)


@pytest.mark.parametrize('field,value',[('raw_text',0),('corrected_text',False)])
def test_non_string_provider_text_is_rejected(tmp_path,field,value):
    from chatvoice import asr_chunks
    source=tmp_path/'source.wav'
    with wave.open(str(source),'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\0\0'*16000)
    result={'raw_text':'text','corrected_text':'text',field:value}
    with pytest.raises(ValueError,match='invalid chunk text'):
        asr_chunks.transcribe_file(source,lambda *args:result)


def test_cancel_after_first_chunk_does_not_continue(tmp_path):
    from chatvoice import asr_chunks
    source=tmp_path/'source.wav';calls=[]
    with wave.open(str(source),'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\0\0'*16000*65)
    def provider(data,index):
        calls.append(index);return {'corrected_text':'first'}
    with pytest.raises(asr_chunks.AudioProcessingCancelled):
        asr_chunks.transcribe_file(source,provider,cancelled=lambda:bool(calls))
    assert calls==[1]


def test_corrupt_container_rejected(tmp_path):
    from chatvoice import asr_chunks
    source=tmp_path/'invalid.wav';source.write_bytes(b'not an audio')
    with pytest.raises(ValueError,match='decoding failed'):
        asr_chunks.transcribe_file(source,lambda *args:pytest.fail('invalid input cannot reach provider'))


def test_asr_temp_write_failure_removes_partial_file(audio_app,monkeypatch,tmp_path):
    import os,tempfile,errno
    real_open=os.fdopen;real_temp=tempfile.mkstemp;created=[]
    def temp(**kwargs):
        fd,name=real_temp(**kwargs);created.append(Path(name));return fd,name
    class FailedTemporary:
        def __init__(self,fd,mode):self.file=real_open(fd,mode)
        def __enter__(self):
            return self
        def write(self,data):
            self.file.write(data[:10]);self.file.flush();raise OSError(errno.ENOSPC,'fixture disk full')
        def __exit__(self,*args):self.file.close()
    monkeypatch.setattr(tempfile,'mkstemp',temp)
    monkeypatch.setattr(os,'fdopen',FailedTemporary)
    with pytest.raises(OSError):audio_app._write_upload_to_temp(b'x'*20,'large.wav')
    assert created and not created[0].exists(), 'failed ASR temp copy must not leak partial file'


def test_large_import_reports_temp_storage_failure(audio_app,monkeypatch):
    import asyncio,httpx,errno
    def fail(*args,**kwargs):raise OSError(errno.ENOSPC,'fixture disk full')
    monkeypatch.setattr(audio_app,'_write_upload_to_temp',fail)
    async def flow():
        from test_meeting_audio_storage import _login
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app),base_url='https://app.example.test') as client:
            csrf=await _login(client,audio_app,'large-storage@example.test')
            result=await client.post('/api/meetings/storage-fail/import',headers=csrf,data={'import_token':'storage-fail-token','channel':'funasr-gpu'},files={'file':('large.wav',padded_wav(),'audio/wav')})
            assert result.status_code==507,result.text
            assert (await client.get('/api/meetings')).json()['meetings']==[]
            assert not list(Path(audio_app.AUDIO_UPLOAD_TEMP_DIR).glob('*'))
    asyncio.run(flow())


def test_import_client_budget_has_explicit_upload_headroom():
    source=(Path(__file__).resolve().parents[1]/'src/chatvoice/web/static/index.html').read_text()
    assert 'setTimeout(() => cancelMeetingAudioImport(), 1800000)' in source
    docs=(Path(__file__).resolve().parents[1]/'docs/recording-storage.en.md').read_text()
    assert 'upload time is separate' not in docs
    assert '30-minute total' in docs


@pytest.mark.parametrize('size',[40000,13*1024*1024])
def test_provider_network_oserror_stays_provider_failure(audio_app,monkeypatch,size):
    import asyncio,httpx,urllib.error
    def provider(*args,**kwargs):raise urllib.error.URLError('fixture network failure')
    monkeypatch.setattr(audio_app,'_api_server_asr',provider)
    async def flow():
        from test_meeting_audio_storage import _login
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app),base_url='https://app.example.test') as client:
            csrf=await _login(client,audio_app,'provider-oserror@example.test')
            result=await client.post('/api/meetings/provider-fail/import',headers=csrf,data={'import_token':'provider-fail-token','channel':'api-server'},files={'file':('sample.wav',padded_wav(size),'audio/wav')})
            assert result.status_code==502,result.text
            assert (await client.get('/api/meetings')).json()['meetings']==[]
            assert not list(Path(audio_app.AUDIO_UPLOAD_TEMP_DIR).glob('*'))
    asyncio.run(flow())
