import tempfile
from unittest.mock import MagicMock, patch

import click
import pytest
from cli.cli import cli
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def temp_file():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("Test content")
        f.flush()
        yield f.name


@pytest.fixture(autouse=True)
def mock_cli_obj(mock_client):
    with patch(
        "cli.commands.ingestion.click.get_current_context"
    ) as mock_context:
        mock_context.return_value.obj = mock_client
        yield


@pytest.fixture(autouse=True)
def mock_r2r_client():
    with patch(
        "cli.command_group.R2RClient", new=MagicMock()
    ) as MockR2RClient:
        mock_client = MockR2RClient.return_value
        mock_client.ingest_files.return_value = {"status": "success"}
        mock_client.update_files.return_value = {"status": "updated"}

        original_callback = cli.callback

        def new_callback(*args, **kwargs):
            ctx = click.get_current_context()
            ctx.obj = mock_client
            return original_callback(*args, **kwargs)

        cli.callback = new_callback

        yield mock_client

        cli.callback = original_callback


def test_ingest_files(runner, mock_r2r_client, temp_file):
    result = runner.invoke(cli, ["ingest-files", temp_file])
    assert result.exit_code == 0
    assert '"status": "success"' in result.output
    mock_r2r_client.ingest_files.assert_called_once_with(
        [temp_file], None, None, None
    )


def test_ingest_files_with_options(runner, mock_r2r_client, temp_file):
    result = runner.invoke(
        cli,
        [
            "ingest-files",
            temp_file,
            "--document-ids",
            "doc1",
            "--metadatas",
            '{"key": "value"}',
            "--versions",
            "v1",
        ],
    )
    assert result.exit_code == 0
    assert '"status": "success"' in result.output
    assert mock_r2r_client.ingest_files.called, "ingest_files was not called"
    mock_r2r_client.ingest_files.assert_called_once_with(
        [temp_file], {"key": "value"}, ["doc1"], ["v1"]
    )


def test_update_files(runner, mock_r2r_client, temp_file):
    result = runner.invoke(
        cli,
        [
            "update-files",
            temp_file,
            "--document-ids",
            "doc1",
            "--metadatas",
            '{"key": "new_value"}',
        ],
    )
    assert result.exit_code == 0
    assert '"status": "updated"' in result.output
    assert mock_r2r_client.update_files.called, "update_files was not called"
    mock_r2r_client.update_files.assert_called_once_with(
        [temp_file], ["doc1"], [{"key": "new_value"}]
    )


@patch("cli.commands.ingestion.ingest_files_from_urls")
def test_ingest_sample_file(mock_ingest, runner, mock_r2r_client):
    mock_ingest.return_value = ["aristotle.txt"]
    result = runner.invoke(cli, ["ingest-sample-file"])
    assert result.exit_code == 0
    assert "Sample file ingestion completed" in result.output
    assert "aristotle.txt" in result.output
    mock_ingest.assert_called_once()


@patch("cli.commands.ingestion.ingest_files_from_urls")
def test_ingest_sample_files(mock_ingest, runner, mock_r2r_client):
    mock_ingest.return_value = ["aristotle.txt", "got.txt"]
    result = runner.invoke(cli, ["ingest-sample-files"])
    assert result.exit_code == 0
    assert "Sample files ingestion completed" in result.output
    assert "aristotle.txt" in result.output
    assert "got.txt" in result.output
    mock_ingest.assert_called_once()


@patch("cli.commands.ingestion.requests.get")
@patch("cli.commands.ingestion.tempfile.NamedTemporaryFile")
def test_ingest_files_from_urls(mock_temp_file, mock_get, mock_r2r_client):
    mock_get.return_value.text = "File content"
    mock_temp_file.return_value.__enter__.return_value.name = "/tmp/test_file"
    mock_r2r_client.ingest_files.return_value = {"status": "success"}

    with patch("cli.commands.ingestion.os.unlink") as mock_unlink:
        from cli.commands.ingestion import ingest_files_from_urls

        result = ingest_files_from_urls(
            mock_r2r_client, ["http://example.com/file.txt"]
        )

    assert result == ["file.txt"]
    mock_r2r_client.ingest_files.assert_called_once_with(["/tmp/test_file"])
    mock_unlink.assert_called_once_with("/tmp/test_file")


def test_ingest_files_with_invalid_file(runner, mock_r2r_client):
    result = runner.invoke(cli, ["ingest-files", "nonexistent_file.txt"])
    assert result.exit_code != 0
    assert "Error" in result.output
    assert not mock_r2r_client.ingest_files.called


def test_update_files_with_invalid_metadata(
    runner, mock_r2r_client, temp_file
):
    result = runner.invoke(
        cli,
        [
            "update-files",
            temp_file,
            "--document-ids",
            "doc1",
            "--metadatas",
            "invalid_json",
        ],
    )
    assert result.exit_code != 0
    assert "Error" in result.output
    assert not mock_r2r_client.update_files.called
