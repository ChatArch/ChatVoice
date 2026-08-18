import os

from click.testing import CliRunner

from chatvoice.cli import main


def test_cli_tree_exposes_token_and_data_commands():
    result = CliRunner().invoke(main, ["--tree"])

    assert result.exit_code == 0, result.output
    assert "tokens" in result.output
    assert "create" in result.output
    assert "revoke" in result.output
    assert "data" in result.output
    assert "meetings" in result.output
    assert "meeting" in result.output
    assert "conversations" in result.output
    assert "conversation" in result.output


def test_cli_data_meetings_reads_token_from_named_env(monkeypatch):
    monkeypatch.setenv("CHATVOICE_DATA_READ", "cv_test_token")
    calls = []

    def fake_list_remote_meetings(base_url, token, *, timeout):
        calls.append((base_url, token, timeout))
        return {"meetings": [{"id": "meeting_1", "title": "周会", "summary_title": "摘要", "transcript_segments": []}]}

    monkeypatch.setattr("chatvoice.cli.list_remote_meetings", fake_list_remote_meetings)

    result = CliRunner().invoke(main, ["data", "meetings", "--url", "http://service.local", "--json"])

    assert result.exit_code == 0, result.output
    assert calls == [("http://service.local", "cv_test_token", 10.0)]
    assert '"meeting_1"' in result.output
    assert "cv_test_token" not in result.output


def test_cli_tokens_create_reads_password_from_named_env(monkeypatch):
    monkeypatch.setenv("CHATVOICE_ACCOUNT_LOGIN", "correct-horse")
    calls = []

    def fake_create_remote_token(base_url, account, password, name, expires_days, scopes, *, timeout):
        calls.append((base_url, account, password, name, expires_days, scopes, timeout))
        return {"token": "cv_once", "token_info": {"id": "tok_1", "name": name, "prefix": "once", "scopes": scopes}}

    monkeypatch.setattr("chatvoice.cli.create_remote_token", fake_create_remote_token)

    result = CliRunner().invoke(
        main,
        [
            "tokens",
            "create",
            "--url",
            "http://service.local",
            "--account",
            "alice@example.invalid",
            "--name",
            "cli",
            "--scope",
            "read:meetings",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [("http://service.local", "alice@example.invalid", "correct-horse", "cli", None, ("read:meetings",), 10.0)]
    assert '"token": "cv_once"' in result.output
    assert "correct-horse" not in result.output


def test_cli_data_requires_token_env(monkeypatch):
    monkeypatch.delenv("CHATVOICE_DATA_READ", raising=False)

    result = CliRunner().invoke(main, ["data", "meetings", "--token-env", "CHATVOICE_DATA_READ"])

    assert result.exit_code != 0
    assert "CHATVOICE_DATA_READ" in result.output
