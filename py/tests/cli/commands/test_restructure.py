from unittest.mock import MagicMock, patch

import asyncclick as click
import pytest
from click.testing import CliRunner

from cli.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture(autouse=True)
def mock_cli_obj(mock_client):
    with patch(
        "cli.commands.restructure.click.get_current_context"
    ) as mock_context:
        mock_context.return_value.obj = mock_client
        yield


@pytest.fixture(autouse=True)
def mock_r2r_client():
    with patch(
        "cli.command_group.R2RClient", new=MagicMock()
    ) as MockR2RClient:
        mock_client = MockR2RClient.return_value

        original_callback = cli.callback

        def new_callback(*args, **kwargs):
            ctx = click.get_current_context()
            ctx.obj = mock_client
            return original_callback(*args, **kwargs)

        cli.callback = new_callback

        yield mock_client

        cli.callback = original_callback


def test_enrich_graph(runner, mock_r2r_client):
    result = runner.invoke(cli, ["enrich-graph"])

    assert result.exit_code == 0
    assert "Time taken" in result.output
    mock_r2r_client.enrich_graph.assert_called_once()
