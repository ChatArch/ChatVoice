from click.testing import CliRunner

from chatvoice.cli import main
from chatvoice.asr import get_asr_channels
from chatvoice.paths import state_paths
from chatvoice.service import render_service_plan


def test_runtime_paths_default_to_chatarch_home(monkeypatch, tmp_path):
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

    assert channels["default"] == "api-server"
    assert channels["channels"]["api-server"]["engine"] == "api"
    assert channels["channels"]["api-server"]["url_configured"] is True
    assert channels["channels"]["api-server"]["api_key_configured"] is True
    assert "secret-value" not in repr(channels)


def test_service_plan_is_importable_and_safe(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.setenv("CHATVOICE_ASR_API_URL", "https://asr.example.invalid/v1/transcribe")
    monkeypatch.setenv("CHATVOICE_DATABASE_URL", "sqlite:///explicit.sqlite3")

    plan = render_service_plan(host="127.0.0.1", port=18087)

    assert plan["command"][0] == "chatvoice"
    assert plan["command"][1:3] == ["serve", "app"]
    assert plan["host"] == "127.0.0.1"
    assert plan["port"] == 18087
    assert plan["asr"]["default"] == "api-server"
    assert plan["database"]["backend"] == "sqlite"
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


def test_cli_service_plan_json(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    result = CliRunner().invoke(main, ["service", "plan", "--json"])

    assert result.exit_code == 0, result.output
    assert '"command"' in result.output
    assert '"database"' in result.output
    assert '"asr"' in result.output
