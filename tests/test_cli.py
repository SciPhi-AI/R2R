from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from r2r.cli.cli import cli
from r2r.cli.utils.param_types import JSON


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_r2r_execution_wrapper():
    with patch("r2r.cli.command_group.R2RExecutionWrapper") as mock:
        yield mock


def test_cli_group(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "R2R CLI for all core operations." in result.output


def test_generate_private_key(runner):
    result = runner.invoke(cli, ["generate-private-key"])
    assert result.exit_code == 0
    assert "Generated Private Key:" in result.output
    assert (
        "Keep this key secure and use it as your R2R_SECRET_KEY."
        in result.output
    )


def test_delete_command(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.delete.return_value = "Deleted successfully"

    result = runner.invoke(cli, ["delete", "--filter", "key1:eq:value1"])
    assert result.exit_code == 0
    assert "Deleted successfully" in result.output
    mock_instance.delete.assert_called_once_with(
        filters={"key1": {"$eq": "value1"}}
    )


def test_multiple_deletes(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.delete.return_value = "Deleted successfully"

    result = runner.invoke(
        cli,
        ["delete", "--filter", "key1:eq:value1", "--filter", "key2:eq:value2"],
    )
    assert result.exit_code == 0
    assert "Deleted successfully" in result.output
    mock_instance.delete.assert_called_once_with(
        filters={"key1": {"$eq": "value1"}, "key2": {"$eq": "value2"}}
    )


def test_documents_overview(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.documents_overview.return_value = [
        "Document 1",
        "Document 2",
    ]

    result = runner.invoke(
        cli,
        [
            "documents-overview",
            "--document-ids",
            "id1",
            "--document-ids",
            "id2",
        ],
    )
    assert result.exit_code == 0
    assert "Document 1" in result.output
    assert "Document 2" in result.output
    mock_instance.documents_overview.assert_called_once_with(["id1", "id2"])


def test_document_chunks(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.document_chunks.return_value = ["Chunk 1", "Chunk 2"]

    result = runner.invoke(cli, ["document-chunks", "doc_id"])
    assert result.exit_code == 0
    assert "Chunk 1" in result.output
    assert "Chunk 2" in result.output
    mock_instance.document_chunks.assert_called_once_with("doc_id")


def test_ingest_files(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.ingest_files.return_value = "Files ingested successfully"

    result = runner.invoke(
        cli,
        [
            "ingest-files",
            "--file-paths",
            "file1.txt",
            "--file-paths",
            "file2.txt",
            "--document-ids",
            "id1",
            "--document-ids",
            "id2",
        ],
    )
    assert result.exit_code == 0
    assert "Files ingested successfully" in result.output
    mock_instance.ingest_files.assert_called_once_with(
        ["file1.txt", "file2.txt"], ["id1", "id2"], None, None
    )


def test_ingest_sample_file(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.ingest_sample_file.return_value = "Sample file ingested"

    result = runner.invoke(
        cli, ["ingest-sample-file", "--no-media", "--option", "1"]
    )
    print(f"Output: {result.output}")
    assert result.exit_code == 0
    assert "Sample file ingested" in result.output
    mock_instance.ingest_sample_file.assert_called_once_with(
        no_media=True, option=1
    )


def test_update_files(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.update_files.return_value = "Files updated successfully"

    result = runner.invoke(
        cli,
        [
            "update-files",
            "file1.txt",
            "--document-ids",
            "id1",
            "--metadatas",
            '{"key": "value"}',
        ],
    )
    assert result.exit_code == 0
    assert "Files updated successfully" in result.output
    mock_instance.update_files.assert_called_once_with(
        ["file1.txt"], ["id1"], ['{"key": "value"}']
    )


def test_analytics(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.analytics.return_value = {"data": "analytics data"}

    result = runner.invoke(
        cli,
        [
            "analytics",
            "--filters",
            '{"date": "2023-01-01"}',
            "--analysis-types",
            '{"type": "usage"}',
        ],
    )
    assert result.exit_code == 0
    assert "{'data': 'analytics data'}" in result.output
    mock_instance.analytics.assert_called_once_with(
        {"date": "2023-01-01"}, {"type": "usage"}
    )


def test_app_settings(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.app_settings.return_value = {"setting1": "value1"}

    result = runner.invoke(cli, ["app-settings"])
    assert result.exit_code == 0
    assert "{'setting1': 'value1'}" in result.output
    mock_instance.app_settings.assert_called_once()


def test_logs(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.logs.return_value = [
        {
            "run_id": "test-run-id",
            "run_type": "test",
            "timestamp": "2024-08-05T20:00:00",
            "user_id": "test-user-id",
            "entries": [{"key": "test-key", "value": "test-value"}],
        }
    ]

    result = runner.invoke(cli, ["logs", "--run-type-filter", "error"])
    assert result.exit_code == 0
    assert "Run ID: test-run-id" in result.output
    assert "Run Type: test" in result.output
    assert "Timestamp: 2024-08-05T20:00:00" in result.output
    assert "User ID: test-user-id" in result.output
    assert "Entries:" in result.output
    assert "  - test-key: test-value" in result.output
    assert "Total runs: 1" in result.output


def test_users_overview(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.users_overview.return_value = ["User 1", "User 2"]

    result = runner.invoke(
        cli,
        [
            "users-overview",
            "--user-ids",
            "123e4567-e89b-12d3-a456-426614174000",
        ],
    )
    assert result.exit_code == 0
    assert "User 1" in result.output
    assert "User 2" in result.output
    mock_instance.users_overview.assert_called_once()


def test_json_param_type():
    result = JSON.convert('{"key": "value"}', param=None, ctx=None)
    assert result == {"key": "value"}

    with pytest.raises(click.BadParameter):
        JSON.convert("invalid json", param=None, ctx=None)

    result = JSON.convert({"key": "value"}, param=None, ctx=None)
    assert result == {"key": "value"}


def test_docker_down_command(runner):
    with patch(
        "r2r.cli.commands.server_operations.bring_down_docker_compose"
    ) as mock_bring_down, patch(
        "r2r.cli.commands.server_operations.remove_r2r_network"
    ) as mock_remove_network:

        mock_bring_down.return_value = 0
        result = runner.invoke(cli, ["docker-down"])
        assert result.exit_code == 0
        assert (
            "Docker Compose setup has been successfully brought down."
            in result.output
        )
        mock_bring_down.assert_called_once()
        mock_remove_network.assert_called_once()

        # legacy code
        # mock_bring_down.return_value = 1
        # result = runner.invoke(cli, ["docker-down"])
        # assert result.exit_code == 0
        # assert (
        #     "An error occurred while bringing down the Docker Compose setup."
        #     in result.output
        # )
        # mock_remove_network.assert_called_once()


def test_generate_report_command():
    runner = CliRunner()
    with patch("subprocess.check_output") as mock_check_output, patch(
        "platform.system"
    ) as mock_system, patch("platform.release") as mock_release, patch(
        "platform.version"
    ) as mock_version, patch(
        "platform.machine"
    ) as mock_machine, patch(
        "platform.processor"
    ) as mock_processor:

        mock_check_output.side_effect = [
            "container1\tname1\tUp 2 hours\n",
            "network1\tnetwork_name1\n",
            "172.17.0.0/16\n",
        ]
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.4.0"
        mock_version.return_value = "#1 SMP Thu Jun 18 12:34:56 UTC 2020"
        mock_machine.return_value = "x86_64"
        mock_processor.return_value = "x86_64"

        result = runner.invoke(cli, ["generate-report"])
        assert result.exit_code == 0
        assert "System Report:" in result.output
        assert "r2r_version" in result.output
        assert "docker_ps" in result.output
        assert "docker_subnets" in result.output
        assert "os_info" in result.output


def test_health_command(runner, mock_r2r_execution_wrapper):
    mock_instance = mock_r2r_execution_wrapper.return_value
    mock_instance.health.return_value = "Server is healthy"

    result = runner.invoke(cli, ["health"])
    assert result.exit_code == 0
    assert "Server is healthy" in result.output
    mock_instance.health.assert_called_once()


def test_update_command(runner):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Successfully updated R2R"
        result = runner.invoke(cli, ["update"])
        assert result.exit_code == 0
        assert "Successfully updated R2R" in result.output
        assert "R2R has been successfully updated." in result.output


def test_version_command(runner):
    with patch("importlib.metadata.version") as mock_version:
        mock_version.return_value = "1.0.0"
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output
