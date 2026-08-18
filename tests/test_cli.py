from click.testing import CliRunner

from chatvoice import __version__
from chatvoice.cli import main


def test_version_option_reports_package_version():
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert f"chatvoice, version {__version__}" in result.output


def test_tree_option_prints_registered_cli_tree():
    result = CliRunner().invoke(main, ["--tree"])

    assert result.exit_code == 0, result.output
    assert "chatvoice  # ChatVoice command line interface" in result.output
    assert "├── --help  # Show help for the current command." in result.output
    assert "├── --version  # Show package version." in result.output
    assert "├── --tree  # Print the registered CLI tree." in result.output
    assert "paths" in result.output
    assert "serve" in result.output
    assert "service" in result.output
