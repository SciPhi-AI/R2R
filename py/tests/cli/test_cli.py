import pytest
from cli.cli import cli, main
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_group_exists():
    assert callable(cli)
    assert cli.name == "cli"


def test_main_function(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.output


def test_commands_added():
    commands = [
        "generate-private-key",
        "ingest-files",
        "update-files",
        "ingest-sample-file",
        "ingest-sample-files",
        "analytics",
        "app-settings",
        "users-overview",
        "documents-overview",
        "document-chunks",
        "inspect-knowledge-graph",
        "enrich-graph",
        "search",
        "rag",
        "health",
        "server-stats",
        "logs",
        "docker-down",
        "generate-report",
        "serve",
        "update",
        "version",
    ]
    for command in commands:
        assert command in cli.commands
