"""Persistent meeting capture mode is a one-way session contract."""

import asyncio
from contextlib import closing

import httpx

from test_meeting_audio_storage import audio_app, _login, _meeting_payload, _wav_bytes


def test_capture_mode_locks_before_transcript_and_rejects_late_switch_or_append(audio_app):
    async def flow():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=audio_app.app), base_url="https://app.example.test"
        ) as client:
            csrf = await _login(client, audio_app, "mode-owner@example.test")
            path = "/api/meetings/mode-lock"
            created = await client.put(path, headers=csrf, json=_meeting_payload(meeting_mode="recording"))
            assert created.status_code == 200
            assert created.json()["capture_state"] == "blank"
            assert created.json()["mode_locked"] is False

            started = await client.post(
                path + "/capture/start",
                headers=csrf,
                json={"meeting_mode": "recording", "capture_token": "capture-token-0001"},
            )
            assert started.status_code == 200, started.text
            assert started.json()["meeting"]["mode_locked"] is True
            assert started.json()["meeting"]["capture_state"] == "started"
            assert started.json()["meeting"]["transcript_segments"] == []

            omitted = await client.put(path, headers=csrf, json=_meeting_payload(title="仍可保存文字"))
            assert omitted.status_code == 200
            assert omitted.json()["meeting_mode"] == "recording"
            malicious = await client.put(
                path, headers=csrf, json=_meeting_payload(meeting_mode="recognition", audio_retention=False)
            )
            assert malicious.status_code == 409
            repeated = await client.post(
                path + "/capture/start",
                headers=csrf,
                json={"meeting_mode": "recording", "capture_token": "another-capture-token"},
            )
            assert repeated.status_code == 409
            attached = await client.post(
                path + "/import", headers=csrf, data={"import_token": "late-import-token"},
                files={"file": ("late.wav", _wav_bytes(), "audio/wav")},
            )
            assert attached.status_code == 409

            finished = await client.post(
                path + "/capture/finish", headers=csrf, json={"capture_token": "capture-token-0001"}
            )
            assert finished.status_code == 200
            reopened = await client.get(path)
            assert reopened.json()["capture_state"] == "finished"
            assert reopened.json()["mode_locked"] is True
            assert (await client.delete(path + "/audio", headers=csrf)).status_code == 200
            still_locked = await client.post(
                path + "/capture/start", headers=csrf,
                json={"meeting_mode": "recording", "capture_token": "after-clear-token"},
            )
            assert still_locked.status_code == 409

    asyncio.run(asyncio.wait_for(flow(), 15))


def test_recognition_route_has_no_replay_and_recording_tail_is_owned_and_idempotent(audio_app):
    async def flow():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=audio_app.app), base_url="https://app.example.test"
        ) as client:
            csrf = await _login(client, audio_app, "routes-owner@example.test")
            pure = "/api/meetings/pure-route"
            assert (await client.put(pure, headers=csrf, json=_meeting_payload(meeting_mode="recognition"))).status_code == 200
            assert (await client.post(pure + "/capture/start", headers=csrf, json={
                "meeting_mode": "recognition", "capture_token": "pure-capture-token"
            })).status_code == 200
            forbidden = await client.post(
                pure + "/audio", headers=csrf,
                data={"upload_token": "pure-upload-token", "capture_token": "pure-capture-token"},
                files={"file": ("pure.wav", _wav_bytes(), "audio/wav")},
            )
            assert forbidden.status_code == 409
            assert (await client.get(pure)).json()["audio_assets"] == []
            gain_media = await client.put(
                pure, headers=csrf, json=_meeting_payload(meeting_mode="recording", audio_retention=True)
            )
            assert gain_media.status_code == 409

            retained = "/api/meetings/recording-route"
            assert (await client.put(retained, headers=csrf, json=_meeting_payload(meeting_mode="recording"))).status_code == 200
            assert (await client.post(retained + "/capture/start", headers=csrf, json={
                "meeting_mode": "recording", "capture_token": "recording-capture-token"
            })).status_code == 200
            form = {"upload_token": "recording-upload-token", "capture_token": "recording-capture-token"}
            files = {"file": ("tail.wav", _wav_bytes(), "audio/wav")}
            saved = await client.post(retained + "/audio", headers=csrf, data=form, files=files)
            assert saved.status_code == 201, saved.text
            assert (await client.post(
                retained + "/capture/finish", headers=csrf,
                json={"capture_token": "recording-capture-token"},
            )).status_code == 200
            duplicate = await client.post(retained + "/audio", headers=csrf, data=form, files=files)
            assert duplicate.status_code == 200
            assert duplicate.json()["duplicate"] is True
            wrong = await client.post(retained + "/audio", headers=csrf, data={
                "upload_token": "other-upload-token", "capture_token": "wrong-capture-token"
            }, files=files)
            assert wrong.status_code == 409

    asyncio.run(asyncio.wait_for(flow(), 15))


def test_import_is_always_recording_route_and_legacy_rows_fail_closed(audio_app, monkeypatch):
    monkeypatch.setattr(audio_app, "transcribe_audio_bytes", lambda *a, **k: {"corrected_text": "导入测试"})

    async def flow():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=audio_app.app), base_url="https://app.example.test"
        ) as client:
            csrf = await _login(client, audio_app, "import-mode@example.test")
            imported = await client.post(
                "/api/meetings/import-mode/import", headers=csrf,
                data={"import_token": "import-mode-token", "retain_audio": "false"},
                files={"file": ("source.wav", _wav_bytes(), "audio/wav")},
            )
            assert imported.status_code == 201, imported.text
            meeting = imported.json()["meeting"]
            assert meeting["meeting_mode"] == "recording"
            assert meeting["mode_locked"] is True
            assert meeting["capture_state"] == "finished"
            assert meeting["audio_retention"] is True
            assert len(meeting["audio_assets"]) == 1

        # A pre-migration record is never treated as a blank meeting that may gain media.
        with closing(audio_app._meeting_db()) as database:
            owner_id = database.execute(
                "SELECT id FROM accounts WHERE account = ?", ("import-mode@example.test",)
            ).fetchone()["id"]
            row = database.execute(
                "SELECT * FROM meeting_records WHERE owner_id = ? AND meeting_id = ?",
                (owner_id, "import-mode"),
            ).fetchone()
            assert row["mode_locked"] == 1

    asyncio.run(asyncio.wait_for(flow(), 15))


def test_text_written_before_capture_also_locks_pure_mode(audio_app):
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url="https://app.example.test") as client:
            csrf = await _login(client, audio_app, "text-first@example.test")
            path = "/api/meetings/text-first"
            text = _meeting_payload(meeting_mode="recognition")
            text["transcript_segments"] = [{"speaker": "甲", "time": "00:00", "text": "已开始转写"}]
            created = await client.put(path, headers=csrf, json=text)
            assert created.status_code == 200, created.text
            assert created.json()["mode_locked"] is True
            assert (await client.put(path, headers=csrf, json=_meeting_payload(meeting_mode="recording"))).status_code == 409
            assert (await client.post(path + "/capture/start", headers=csrf, json={
                "meeting_mode": "recognition", "capture_token": "text-first-token"
            })).status_code == 409
    asyncio.run(asyncio.wait_for(flow(), 15))


def test_second_distinct_audio_upload_cannot_append_during_capture(audio_app):
    async def flow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=audio_app.app), base_url="https://app.example.test") as client:
            csrf = await _login(client, audio_app, "single-asset@example.test")
            path = "/api/meetings/single-asset"
            assert (await client.put(path, headers=csrf, json=_meeting_payload(meeting_mode="recording"))).status_code == 200
            assert (await client.post(path + "/capture/start", headers=csrf, json={
                "meeting_mode": "recording", "capture_token": "single-asset-capture"
            })).status_code == 200
            first = await client.post(path + "/audio", headers=csrf, data={
                "upload_token": "first-upload", "capture_token": "single-asset-capture"
            }, files={"file": ("one.wav", _wav_bytes(), "audio/wav")})
            assert first.status_code == 201, first.text
            second = await client.post(path + "/audio", headers=csrf, data={
                "upload_token": "second-upload", "capture_token": "single-asset-capture"
            }, files={"file": ("two.wav", _wav_bytes(), "audio/wav")})
            assert second.status_code == 409, second.text
            assert len((await client.get(path)).json()["audio_assets"]) == 1
    asyncio.run(asyncio.wait_for(flow(), 15))
