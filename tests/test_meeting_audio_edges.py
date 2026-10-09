import asyncio
from pathlib import Path

import httpx

from test_meeting_audio_storage import audio_app, _login, _wav_bytes, _meeting_payload, _start_capture


def test_audio_upload_limit_applies_before_multipart_and_auth(audio_app, monkeypatch):
    monkeypatch.setattr(audio_app, 'MAX_IMPORTED_AUDIO_BYTES', 8)
    monkeypatch.setattr(audio_app, 'AUDIO_UPLOAD_ENVELOPE_BYTES', 16, raising=False)
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url='https://app.example.test') as client:
            r = await client.post('/api/meetings/oversize/import', content=b'x' * 70, headers={'Content-Type':'multipart/form-data; boundary=test'})
            assert r.status_code == 413
    asyncio.run(asyncio.wait_for(flow(), 5))


def test_clear_during_staging_rejects_late_recording_commit(audio_app, monkeypatch):
    staged_event = asyncio.Event()
    release = asyncio.Event()
    original = audio_app._stage_audio_upload
    async def stage(*args, **kwargs):
        result = await original(*args, **kwargs)
        staged_event.set()
        await release.wait()
        return result
    monkeypatch.setattr(audio_app, '_stage_audio_upload', stage)
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url='https://app.example.test') as client:
            csrf = await _login(client, audio_app, 'clear-race@example.test')
            path = '/api/meetings/clear-race'
            assert (await client.put(path, headers=csrf, json=_meeting_payload(audio_retention=True))).status_code == 200
            capture = await _start_capture(client, path, csrf, 'clear-race-capture')
            uploading = asyncio.create_task(client.post(path + '/audio', headers=csrf, data={'upload_token':'clear-race-token','capture_token':capture}, files={'file':('x.wav',_wav_bytes(),'audio/wav')}))
            await staged_event.wait()
            try:
                assert (await client.delete(path + '/audio', headers=csrf)).status_code == 200
            finally:
                release.set()
            assert (await uploading).status_code == 409
            assert (await client.get(path)).json()['audio_assets'] == []
            assert not list(Path(audio_app.MEETING_AUDIO_DIR).glob('*'))
            assert not list(Path(audio_app.AUDIO_UPLOAD_TEMP_DIR).glob('*'))
    asyncio.run(asyncio.wait_for(flow(), 10))


def test_recording_from_before_clear_cannot_be_saved_after_clear(audio_app):
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url='https://app.example.test') as client:
            csrf = await _login(client, audio_app, 'old-generation@example.test')
            path = '/api/meetings/old-generation'
            assert (await client.put(path, headers=csrf, json=_meeting_payload(audio_retention=True))).status_code == 200
            capture = await _start_capture(client, path, csrf, 'old-generation-capture')
            assert (await client.delete(path + '/audio', headers=csrf)).status_code == 200
            r = await client.post(path + '/audio', headers=csrf, data={'upload_token':'old-generation-token','capture_token':capture,'generation':'0'}, files={'file':('x.wav',_wav_bytes(),'audio/wav')})
            assert r.status_code == 409
    asyncio.run(asyncio.wait_for(flow(), 10))


def test_chunked_upload_limit_is_not_bypassed_by_missing_content_length(audio_app, monkeypatch):
    monkeypatch.setattr(audio_app, 'MAX_IMPORTED_AUDIO_BYTES', 8)
    monkeypatch.setattr(audio_app, 'AUDIO_UPLOAD_ENVELOPE_BYTES', 16, raising=False)
    body = b'--test\r\nContent-Disposition: form-data; name="import_token"\r\n\r\nchunked-token\r\n--test\r\nContent-Disposition: form-data; name="file"; filename="x.wav"\r\nContent-Type: audio/wav\r\n\r\n' + _wav_bytes() + b'\r\n--test--\r\n'
    async def chunks():
        yield body[:12]
        yield body[12:]
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url='https://app.example.test') as client:
            r = await client.post('/api/meetings/chunked/import', content=chunks(), headers={'Content-Type':'multipart/form-data; boundary=test'})
            assert r.status_code == 413
    asyncio.run(asyncio.wait_for(flow(), 5))


def test_recording_move_then_permission_failure_removes_target_file(audio_app, monkeypatch):
    original = Path.chmod
    def permission(path, *args, **kwargs):
        if path.parent == Path(audio_app.MEETING_AUDIO_DIR) and path.name.startswith('audio_'):
            raise PermissionError('fixture target permission failure')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'chmod', permission)
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app, raise_app_exceptions=False), base_url='https://app.example.test') as client:
            csrf = await _login(client, audio_app, 'recording-storage-failure@example.test')
            path = '/api/meetings/recording-storage-failure'
            assert (await client.put(path, headers=csrf, json=_meeting_payload(audio_retention=True))).status_code == 200
            capture = await _start_capture(client, path, csrf, 'storage-failure-capture')
            response = await client.post(path + '/audio', headers=csrf, data={'upload_token':'recording-storage-failure-token','capture_token':capture}, files={'file':('x.wav',_wav_bytes(),'audio/wav')})
            assert response.status_code == 503
            assert not list(Path(audio_app.MEETING_AUDIO_DIR).glob('*'))
            assert (await client.get(path)).json()['audio_assets'] == []
    asyncio.run(asyncio.wait_for(flow(), 10))


def test_import_storage_failure_rolls_back_meeting_and_files(audio_app, monkeypatch):
    monkeypatch.setattr(audio_app, 'transcribe_audio_bytes', lambda *a, **k: {'corrected_text':'存储故障测试'})
    def fail(*args, **kwargs):
        raise OSError('fixture storage failure')
    monkeypatch.setattr(audio_app, '_audio_storage_path', fail)
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app, raise_app_exceptions=False), base_url='https://app.example.test') as client:
            csrf = await _login(client, audio_app, 'storage-failure@example.test')
            response = await client.post('/api/meetings/storage-failure/import', headers=csrf,
                data={'import_token':'storage-failure-token','retain_audio':'true'}, files={'file':('x.wav',_wav_bytes(),'audio/wav')})
            assert response.status_code == 503
            assert (await client.get('/api/meetings/storage-failure')).status_code == 404
            assert not list(Path(audio_app.MEETING_AUDIO_DIR).glob('*'))
            assert not list(Path(audio_app.AUDIO_UPLOAD_TEMP_DIR).glob('*'))
    asyncio.run(asyncio.wait_for(flow(), 10))
