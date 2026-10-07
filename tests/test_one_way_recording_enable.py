import asyncio

import httpx

from test_meeting_audio_storage import audio_app, _login, _meeting_payload


def test_recording_enable_is_irreversible_before_start_but_can_start_once(audio_app):
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url='https://app.example.test') as client:
            csrf = await _login(client, audio_app, 'enable-once@example.test')
            path = '/api/meetings/enable-once'
            blank = await client.put(path, headers=csrf, json=_meeting_payload(meeting_mode='recognition'))
            assert blank.status_code == 200 and blank.json()['mode_locked'] is False
            enabled = await client.put(path, headers=csrf, json=_meeting_payload(meeting_mode='recording'))
            assert enabled.status_code == 200, enabled.text
            assert enabled.json()['mode_locked'] is True
            assert enabled.json()['capture_state'] == 'blank'
            reopened = await client.get(path)
            assert reopened.json()['meeting_mode'] == 'recording' and reopened.json()['mode_locked']
            rejected = await client.put(path, headers=csrf, json=_meeting_payload(meeting_mode='recognition', audio_retention=False))
            assert rejected.status_code == 409
            started = await client.post(path + '/capture/start', headers=csrf, json={'meeting_mode':'recording','capture_token':'one-way-capture'})
            assert started.status_code == 200, started.text
            repeated = await client.post(path + '/capture/start', headers=csrf, json={'meeting_mode':'recording','capture_token':'different-capture'})
            assert repeated.status_code == 409
    asyncio.run(asyncio.wait_for(flow(), 15))
