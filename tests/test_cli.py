from click.testing import CliRunner
from chatstyle import render_click_tree

from chatvoice import __version__
from chatvoice.cli import main


def test_root_name_and_help_expose_shared_tree_options():
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert main.name == "chatvoice"
    assert "--tree" in result.output
    assert "--tree-brief" in result.output


def test_version_option_reports_package_version():
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert f"chatvoice, version {__version__}" in result.output


def test_tree_option_prints_registered_cli_tree():
    result = CliRunner().invoke(main, ["--tree"])

    assert result.exit_code == 0, result.output
    assert result.output.rstrip() == render_click_tree(main, root_name="chatvoice")
    assert result.output.splitlines().count("chatvoice") == 1
    assert "├── --tree  # Print the registered CLI tree and exit." in result.output
    assert "├── --tree-brief  # Print the registered CLI tree without parameter signatures and exit." in result.output
    assert "add <ACCOUNT>" in result.output
    assert "--password-env" in result.output


def test_tree_brief_prints_same_nodes_without_signatures():
    full = CliRunner().invoke(main, ["--tree"])
    brief = CliRunner().invoke(main, ["--tree-brief"])

    assert full.exit_code == brief.exit_code == 0
    assert brief.output.rstrip() == render_click_tree(main, root_name="chatvoice", brief=True)
    assert brief.output.splitlines().count("chatvoice") == 1
    assert "accounts" in brief.output
    assert "add  # Create one invited account" in brief.output
    assert "<ACCOUNT>" not in brief.output
    assert "--password-env" not in brief.output
