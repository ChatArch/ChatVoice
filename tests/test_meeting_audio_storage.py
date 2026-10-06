"""Owner-scoped retained meeting audio uses the real auth and meeting routes."""

from __future__ import annotations

import asyncio
from contextlib import closing
import importlib
import io
import os
from pathlib import Path
import sqlite3
import stat
import sys
import wave

import fastapi.routing
import httpx
import pytest


def _wav_bytes(frames: int = 800) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\0\0" * frames)
    return output.getvalue()


@pytest.fixture
def audio_app(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch"))
    monkeypatch.setenv("CHATVOICE_HOME", str(tmp_path / "voice"))
    monkeypatch.setenv("CHATVOICE_ASR_CHANNEL", "stub-local")
    monkeypatch.setenv("CHATVOICE_ASR_PREWARM", "0")
    sys.modules.pop("chatvoice.web.legacy_app", None)
    module = importlib.import_module("chatvoice.web.legacy_app")
    monkeypatch.setattr(module, "MEETING_DB_PATH", tmp_path / "meetings.sqlite3")
    monkeypatch.setattr(module, "MEETING_AUDIO_DIR", tmp_path / "private-audio", raising=False)
    monkeypatch.setattr(module, "AUDIO_UPLOAD_TEMP_DIR", tmp_path / "audio-upload-temp", raising=False)
    yield module
    sys.modules.pop("chatvoice.web.legacy_app", None)


async def _login(client: httpx.AsyncClient, module, account: str) -> dict[str, str]:
    module.provision_managed_account(account, "test-only-password", account)
    response = await client.post(
        "/api/auth/login",
        json={"account": account, "password": "test-only-password"},
    )
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def _meeting_payload(**extra):
    return {
        "title": "保留测试",
        "created_at": "2026-10-06T00:00:00Z",
        "updated_at": "2026-10-06T00:00:00Z",
        **extra,
    }


def test_audio_retention_defaults_off_and_omission_preserves_explicit_choice(audio_app):
    async def flow():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=audio_app.app),
            base_url="https://app.example.test",
        ) as client:
            csrf = await _login(client, audio_app, "owner-default@example.test")
            path = "/api/meetings/retention-default"
            created = await client.put(path, headers=csrf, json=_meeting_payload())
            assert created.status_code == 200
            assert created.json().get("audio_retention") is False
            assert created.json().get("audio_assets") == []

            enabled = await client.put(path, headers=csrf, json=_meeting_payload(audio_retention=True))
            assert enabled.status_code == 200
            assert enabled.json().get("audio_retention") is True

            legacy_save = await client.put(path, headers=csrf, json=_meeting_payload(title="旧客户端保存"))
            assert legacy_save.status_code == 200
            assert legacy_save.json().get("audio_retention") is True

    asyncio.run(asyncio.wait_for(flow(), 15))


def test_retained_audio_finalize_is_private_idempotent_and_deleted_with_meeting(audio_app):
    async def flow():
        transport = httpx.ASGITransport(app=audio_app.app)
        async with (
            httpx.AsyncClient(transport=transport, base_url="https://app.example.test") as anonymous,
            httpx.AsyncClient(transport=transport, base_url="https://app.example.test") as owner,
            httpx.AsyncClient(transport=transport, base_url="https://app.example.test") as other,
        ):
            owner_csrf = await _login(owner, audio_app, "audio-owner@example.test")
            await _login(other, audio_app, "audio-other@example.test")
            meeting_path = "/api/meetings/private-audio"
            assert (await owner.put(meeting_path, headers=owner_csrf, json=_meeting_payload(audio_retention=True))).status_code == 200

            upload_path = meeting_path + "/audio"
            form = {"upload_token": "recording-token-0001"}
            files = {"file": ("../../outside.wav", _wav_bytes(), "audio/wav")}
            assert (await anonymous.post(upload_path, data=form, files=files)).status_code == 401
            assert (await owner.post(upload_path, data=form, files=files)).status_code == 403

            finalized = await owner.post(upload_path, headers=owner_csrf, data=form, files=files)
            assert finalized.status_code == 201, finalized.text
            asset = finalized.json()["audio"]
            assert asset["source"] == "recording"
            assert asset["media_type"] == "audio/wav"
            assert asset["size_bytes"] == len(_wav_bytes())
            assert asset["stream_url"].endswith(f"/audio/{asset['id']}")
            assert asset["download_url"].endswith(f"/audio/{asset['id']}/download")

            stored_files = list(Path(audio_app.MEETING_AUDIO_DIR).iterdir())
            assert len(stored_files) == 1
            stored = stored_files[0]
            assert stored.name != "outside.wav"
            assert stored.parent.resolve() == Path(audio_app.MEETING_AUDIO_DIR).resolve()
            assert stat.S_IMODE(stored.stat().st_mode) == 0o600
            assert stat.S_IMODE(Path(audio_app.MEETING_AUDIO_DIR).stat().st_mode) == 0o700

            stream_path = asset["stream_url"]
            assert (await anonymous.get(stream_path)).status_code == 401
            assert (await other.get(stream_path)).status_code == 404
            streamed = await owner.get(stream_path)
            assert streamed.status_code == 200
            assert streamed.content == _wav_bytes()
            assert streamed.headers["content-type"].startswith("audio/wav")
            assert streamed.headers["x-content-type-options"] == "nosniff"
            assert "private" in streamed.headers["cache-control"]

            downloaded = await owner.get(asset["download_url"])
            assert downloaded.status_code == 200
            assert "attachment" in downloaded.headers["content-disposition"]
            assert "outside" not in downloaded.headers["content-disposition"]

            duplicate = await owner.post(upload_path, headers=owner_csrf, data=form, files=files)
            assert duplicate.status_code == 200
            assert duplicate.json()["duplicate"] is True
            assert duplicate.json()["audio"]["id"] == asset["id"]
            assert len(list(Path(audio_app.MEETING_AUDIO_DIR).iterdir())) == 1

            deleted = await owner.delete(meeting_path, headers=owner_csrf)
            assert deleted.status_code == 200
            assert deleted.json()["deleted"] is True
            assert not stored.exists()
            assert (await owner.get(stream_path)).status_code == 404

    asyncio.run(asyncio.wait_for(flow(), 20))


def test_audio_upload_rejects_empty_invalid_and_oversize_without_files(audio_app, monkeypatch):
    async def flow():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=audio_app.app),
            base_url="https://app.example.test",
        ) as client:
            csrf = await _login(client, audio_app, "audio-validation@example.test")
            path = "/api/meetings/validation"
            assert (await client.put(path, headers=csrf, json=_meeting_payload(audio_retention=True))).status_code == 200
            upload_path = path + "/audio"

            empty = await client.post(
                upload_path,
                headers=csrf,
                data={"upload_token": "empty-token-0001"},
                files={"file": ("empty.wav", b"", "audio/wav")},
            )
            assert empty.status_code == 400

            invalid = await client.post(
                upload_path,
                headers=csrf,
                data={"upload_token": "invalid-token-01"},
                files={"file": ("notes.wav", b"not audio", "audio/wav")},
            )
            assert invalid.status_code == 415

            monkeypatch.setattr(audio_app, "MAX_RETAINED_AUDIO_BYTES", 64, raising=False)
            oversized = await client.post(
                upload_path,
                headers=csrf,
                data={"upload_token": "oversize-token-1"},
                files={"file": ("large.wav", _wav_bytes(), "audio/wav")},
            )
            assert oversized.status_code == 413
            assert not Path(audio_app.MEETING_AUDIO_DIR).exists() or not list(Path(audio_app.MEETING_AUDIO_DIR).iterdir())
            assert not Path(audio_app.AUDIO_UPLOAD_TEMP_DIR).exists() or not list(Path(audio_app.AUDIO_UPLOAD_TEMP_DIR).iterdir())

    asyncio.run(asyncio.wait_for(flow(), 15))


def test_audio_schema_migrates_legacy_meetings_and_reset_cleanup(audio_app):
    with sqlite3.connect(audio_app.MEETING_DB_PATH) as database:
        database.execute(
            """CREATE TABLE meeting_records (
              owner_id TEXT NOT NULL, meeting_id TEXT NOT NULL, title TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              duration_seconds INTEGER NOT NULL DEFAULT 0,
              transcript_json TEXT NOT NULL DEFAULT '[]',
              summary_title TEXT NOT NULL DEFAULT '', summary_content TEXT NOT NULL DEFAULT '',
              preview TEXT NOT NULL DEFAULT '', PRIMARY KEY (owner_id, meeting_id))"""
        )
        database.execute(
            "INSERT INTO meeting_records(owner_id, meeting_id, title, created_at, updated_at) "
            "VALUES('legacy-owner', 'legacy-meeting', '旧会议', 'now', 'now')"
        )

    with closing(audio_app._meeting_db()) as database:
        columns = {row[1] for row in database.execute("PRAGMA table_info(meeting_records)")}
        assert {"audio_retention", "import_token"} <= columns
        table = database.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meeting_audio_assets'"
        ).fetchone()
        assert table is not None
        row = database.execute("SELECT * FROM meeting_records WHERE meeting_id='legacy-meeting'").fetchone()
        payload = audio_app._meeting_row_payload(row, True, audio_assets=[])
        assert payload["audio_retention"] is False
        assert payload["audio_assets"] == []
