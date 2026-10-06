"""Audio import exercises real auth/storage/ASR dispatch; only provider is replaced."""
import asyncio
import threading
from pathlib import Path

import httpx
import pytest

from test_meeting_audio_storage import audio_app, _login, _wav_bytes


@pytest.mark.parametrize('retain', [False, True])
def test_import_creates_normal_meeting_and_only_retains_on_explicit_request(audio_app, monkeypatch, retain):
    calls = []
    def provider(channel, audio_bytes, filename, correct=True):
        calls.append((channel, audio_bytes))
        return {'raw_text': '导入音频的测试转写', 'corrected_text': '导入音频的测试转写', 'engine': 'provider-fixture'}
    monkeypatch.setattr(audio_app, 'transcribe_audio_bytes', provider)
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url='https://app.example.test') as client:
            csrf = await _login(client, audio_app, 'import-owner@example.test')
            path = '/api/meetings/import-one/import'
            data = {'import_token': 'import-token-0001', 'retain_audio': str(retain).lower(), 'channel': 'stub-local'}
            files = {'file': ('../../会议.wav', _wav_bytes(), 'audio/wav')}
            imported = await client.post(path, headers=csrf, data=data, files=files)
            assert imported.status_code == 201, imported.text
            meeting = imported.json()['meeting']
            assert meeting['id'] == 'import-one'
            assert meeting['audio_retention'] is retain
            assert meeting['transcript_segments'][0]['text'] == '导入音频的测试转写'
            opened = await client.get('/api/meetings/import-one')
            assert opened.status_code == 200
            assert opened.json()['transcript_segments'] == meeting['transcript_segments']
            assert len(opened.json()['audio_assets']) == int(retain)
            saved_files = list(Path(audio_app.MEETING_AUDIO_DIR).glob('*'))
            assert len(saved_files) == int(retain)
            if retain:
                asset = opened.json()['audio_assets'][0]
                assert asset['source'] == 'import'
                assert (await client.get(asset['download_url'])).content == _wav_bytes()
            duplicate = await client.post(path, headers=csrf, data=data, files=files)
            assert duplicate.status_code == 200
            assert duplicate.json()['duplicate'] is True
            assert len(calls) == 1
            assert calls[0][0] == 'stub-local' and calls[0][1] == _wav_bytes()
            assert not list(Path(audio_app.AUDIO_UPLOAD_TEMP_DIR).glob('*'))
    asyncio.run(asyncio.wait_for(flow(), 10))


@pytest.mark.parametrize('failure', ['empty', 'error', 'invalid'])
def test_import_provider_failure_does_not_leave_meeting_or_recording(audio_app, monkeypatch, failure):
    def provider(*args, **kwargs):
        if failure == 'error':
            raise RuntimeError('provider-fixture failure')
        if failure == 'invalid':
            return {'corrected_text': {'not': 'transcript'}}
        return {'corrected_text': '', 'raw_text': ''}
    monkeypatch.setattr(audio_app, 'transcribe_audio_bytes', provider)
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url='https://app.example.test') as client:
            csrf = await _login(client, audio_app, 'import-failure@example.test')
            response = await client.post('/api/meetings/import-failed/import', headers=csrf,
                data={'import_token': 'import-failed-token', 'retain_audio': 'true'}, files={'file': ('x.wav', _wav_bytes(), 'audio/wav')})
            assert response.status_code == 502, response.text
            assert (await client.get('/api/meetings/import-failed')).status_code == 404
            assert not list(Path(audio_app.MEETING_AUDIO_DIR).glob('*'))
            assert not list(Path(audio_app.AUDIO_UPLOAD_TEMP_DIR).glob('*'))
    asyncio.run(asyncio.wait_for(flow(), 10))


def test_long_import_remains_saveable_through_normal_meeting_api(audio_app, monkeypatch):
    text = '长会议文字' * 1600
    monkeypatch.setattr(audio_app, 'transcribe_audio_bytes', lambda *a, **k: {'corrected_text':text})
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url='https://app.example.test') as client:
            csrf = await _login(client, audio_app, 'long-import@example.test')
            r = await client.post('/api/meetings/long-import/import', headers=csrf, data={'import_token':'long-import-token'}, files={'file':('x.wav',_wav_bytes(),'audio/wav')})
            assert r.status_code == 201
            record = r.json()['meeting']
            assert ''.join(s['text'] for s in record['transcript_segments']) == text
            assert all(len(s['text']) <= 5000 for s in record['transcript_segments'])
            assert (await client.put('/api/meetings/long-import', headers=csrf, json=record)).status_code == 200
    asyncio.run(asyncio.wait_for(flow(), 10))


def test_import_auth_validation_and_cancel_before_upload(audio_app, monkeypatch):
    monkeypatch.setattr(audio_app, 'transcribe_audio_bytes', lambda *a, **k: pytest.fail('invalid/cancelled input must not reach provider'))
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url='https://app.example.test') as client:
            path = '/api/meetings/input-validation/import'
            fields = {'import_token': 'input-validation-token'}
            wav = {'file': ('x.wav', _wav_bytes(), 'audio/wav')}
            assert (await client.post(path, data=fields, files=wav)).status_code == 401
            csrf = await _login(client, audio_app, 'import-validation@example.test')
            assert (await client.post(path, data=fields, files=wav)).status_code == 403
            for token, body, expected in [('empty-import', b'', 400), ('invalid-import', b'not audio', 415)]:
                r = await client.post(path, headers=csrf, data={'import_token': token}, files={'file': ('x.wav', body, 'audio/wav')})
                assert r.status_code == expected
            cancelled = await client.delete('/api/meeting-imports/cancel-before-upload', headers=csrf)
            assert cancelled.status_code == 200
            r = await client.post(path, headers=csrf, data={'import_token': 'cancel-before-upload'}, files=wav)
            assert r.status_code == 409
            assert (await client.get('/api/meetings/input-validation')).status_code == 404
    asyncio.run(asyncio.wait_for(flow(), 10))


def test_import_cancel_during_asr_cannot_commit_a_ghost_meeting(audio_app, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    def provider(*args, **kwargs):
        started.set()
        assert release.wait(5), 'test provider released cooperatively'
        return {'corrected_text': 'late provider result'}
    monkeypatch.setattr(audio_app, 'transcribe_audio_bytes', provider)
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url='https://app.example.test') as client:
            csrf = await _login(client, audio_app, 'import-cancel@example.test')
            task = asyncio.create_task(client.post('/api/meetings/cancel-during/import', headers=csrf,
                data={'import_token': 'cancel-during-token', 'retain_audio': 'true'}, files={'file': ('x.wav', _wav_bytes(), 'audio/wav')}))
            try:
                assert await asyncio.to_thread(started.wait, 2)
                assert (await client.delete('/api/meeting-imports/cancel-during-token', headers=csrf)).status_code == 200
            finally:
                release.set()
            assert (await task).status_code == 409
            assert (await client.get('/api/meetings/cancel-during')).status_code == 404
            assert not list(Path(audio_app.MEETING_AUDIO_DIR).glob('*'))
            assert not list(Path(audio_app.AUDIO_UPLOAD_TEMP_DIR).glob('*'))
    asyncio.run(asyncio.wait_for(flow(), 10))
