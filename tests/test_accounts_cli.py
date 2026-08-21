from click.testing import CliRunner

from chatvoice.cli import main


def test_accounts_add_and_list_use_packaged_runtime(monkeypatch, tmp_path):
    from chatvoice.web import legacy_app

    monkeypatch.setattr(legacy_app, "MEETING_DB_PATH", tmp_path / "meetings.sqlite3")
    monkeypatch.setenv("CHATVOICE_ACCOUNT_PASSWORD", "correct horse battery")

    runner = CliRunner()
    created = runner.invoke(
        main,
        [
            "accounts",
            "add",
            "person@example.com",
            "--display-name",
            "Person",
            "--password-env",
            "CHATVOICE_ACCOUNT_PASSWORD",
            "--json",
        ],
    )

    assert created.exit_code == 0, created.output
    assert '"account": "person@example.com"' in created.output
    assert 'correct horse battery' not in created.output

    listed = runner.invoke(main, ["accounts", "list", "--json"])

    assert listed.exit_code == 0, listed.output
    assert '"account": "person@example.com"' in listed.output
    assert 'password' not in listed.output.lower()


def test_cli_tree_exposes_account_commands():
    result = CliRunner().invoke(main, ["--tree"])

    assert result.exit_code == 0
    assert "accounts" in result.output
    assert "add <ACCOUNT>" in result.output
    assert "list [--json]" in result.output
