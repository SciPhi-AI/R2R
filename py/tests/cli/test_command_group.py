import pytest
from click.testing import CliRunner

from cli.command_group import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_group_no_options():
    assert len(cli.params) == 0


def test_cli_group_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "R2R CLI for all core operations." in result.output
