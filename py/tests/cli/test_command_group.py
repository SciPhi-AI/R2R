import pytest
from click.testing import CliRunner

from cli.command_group import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_group_options():
    assert "config_path" in [param.name for param in cli.params]
    assert "config_name" in [param.name for param in cli.params]
    assert "base_url" in [param.name for param in cli.params]


def test_cli_group_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "R2R CLI for all core operations." in result.output


def test_base_url_option(runner):
    result = runner.invoke(
        cli, ["--base-url", "http://example.com", "generate-private-key"]
    )
    assert result.exit_code == 0
