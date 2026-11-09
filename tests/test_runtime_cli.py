import json
import sqlite3

from click.testing import CliRunner

from chatvoice.cli import main
from chatvoice.asr import get_asr_channels
from chatvoice.paths import state_paths
from chatvoice.service import render_service_plan


def test_runtime_paths_default_to_chatarch_home(monkeypatch, tmp_path):
    monkeypatch.delenv("CHATVOICE_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("CHATVOICE_HOME", raising=False)
    monkeypatch.delenv("MEETING_DB_PATH", raising=False)
    monkeypatch.delenv("CHATVOICE_SQLITE_PATH", raising=False)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))

    paths = state_paths()

    assert paths.root == tmp_path / "chatarch-home" / "chatvoice"
    assert paths.data_dir == paths.root / "data"
    assert paths.logs_dir == paths.root / "logs"
    assert paths.run_dir == paths.root / "run"
    assert paths.temp_dir == paths.root / "temp"
    assert paths.model_cache_dir == paths.root / "model-cache"
    assert paths.database_path == paths.data_dir / "meetings.sqlite3"


def test_asr_channels_include_api_server_provider(monkeypatch):
    monkeypatch.setenv("CHATVOICE_ASR_API_URL", "https://asr.example.invalid/v1/transcribe")
    monkeypatch.setenv("CHATVOICE_ASR_API_KEY", "secret-value")

    channels = get_asr_channels()

    assert channels["default"] == "auto"
    assert channels["channels"]["volcengine-plan"]["engine"] == "volcengine-ws"
    assert channels["channels"]["api-server"]["engine"] == "api"
    assert channels["channels"]["api-server"]["url_configured"] is True
    assert channels["channels"]["api-server"]["api_key_configured"] is True
    assert "secret-value" not in repr(channels)


def test_service_plan_is_importable_and_safe(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.setenv("CHATVOICE_ASR_API_URL", "https://asr.example.invalid/v1/transcribe")

    plan = render_service_plan(host="127.0.0.1", port=18087)

    assert plan["command"][0] == "chatvoice"
    assert plan["command"][1:3] == ["serve", "app"]
    assert plan["host"] == "127.0.0.1"
    assert plan["port"] == 18087
    assert plan["asr"]["default"] == "auto"
    assert plan["asr"]["channels"]["api-server"]["status"] == "ready"
    assert plan["asr"]["channels"]["api-server"]["url_configured"] is True
    assert plan["database"]["backend"] == "sqlite"
    assert plan["database"]["backup_unit"] == "single-sqlite-file"
    assert plan["database"]["concurrency"] == "single-node-wal"


def test_cli_tree_exposes_runtime_service_and_provider_commands():
    result = CliRunner().invoke(main, ["--tree"])

    assert result.exit_code == 0, result.output
    assert "paths" in result.output
    assert "doctor" in result.output
    assert "serve" in result.output
    assert "app" in result.output
    assert "health" in result.output
    assert "status" in result.output
    assert "asr" in result.output
    assert "channels" in result.output
    assert "service" in result.output
    assert "plan" in result.output
    assert "dump" in result.output
    assert "import" in result.output


def _write_sample_database(path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS sample (value TEXT NOT NULL)")
        connection.execute("DELETE FROM sample")
        connection.execute("INSERT INTO sample(value) VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def _sample_value(path) -> str:
    connection = sqlite3.connect(path)
    try:
        return connection.execute("SELECT value FROM sample").fetchone()[0]
    finally:
        connection.close()


def test_cli_data_dump_and_import_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    database = state_paths().database_path
    _write_sample_database(database, "before")
    dump_path = tmp_path / "backup.sqlite3"

    runner = CliRunner()
    dump_result = runner.invoke(main, ["data", "dump", "--output", str(dump_path), "--json"])

    assert dump_result.exit_code == 0, dump_result.output
    dump_payload = json.loads(dump_result.output)
    assert dump_payload["output"] == str(dump_path)
    assert dump_payload["integrity"] == "ok"
    assert dump_path.exists()

    _write_sample_database(database, "after")
    refused = runner.invoke(main, ["data", "import", str(dump_path)])
    assert refused.exit_code != 0
    assert "--yes" in refused.output

    import_result = runner.invoke(main, ["data", "import", str(dump_path), "--yes", "--json"])

    assert import_result.exit_code == 0, import_result.output
    import_payload = json.loads(import_result.output)
    assert import_payload["database"] == str(database)
    assert import_payload["backup"]
    assert import_payload["integrity"] == "ok"
    assert _sample_value(database) == "before"


def test_cli_service_plan_json(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    result = CliRunner().invoke(main, ["service", "plan", "--json"])

    assert result.exit_code == 0, result.output
    assert '"command"' in result.output
    assert '"database"' in result.output
    assert '"asr"' in result.output
