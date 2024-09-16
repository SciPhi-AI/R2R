import json
from unittest.mock import MagicMock, patch

import asyncclick as click
import pytest
from click.testing import CliRunner

from cli.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_r2r_client():
    with patch(
        "cli.command_group.R2RClient", new=MagicMock()
    ) as MockR2RClient:
        mock_client = MockR2RClient.return_value
        mock_client.analytics.return_value = {
            "status": "success",
            "result": "analytics data",
        }
        mock_client.app_settings.return_value = {
            "setting1": "value1",
            "setting2": "value2",
        }
        mock_client.users_overview.return_value = [
            {"id": "user1", "name": "John"},
            {"id": "user2", "name": "Jane"},
        ]
        mock_client.delete.return_value = {"deleted": 2}
        mock_client.documents_overview.return_value = {
            "results": [
                {"id": "doc1", "title": "Document 1"},
                {"id": "doc2", "title": "Document 2"},
            ]
        }
        mock_client.document_chunks.return_value = {
            "results": [
                {
                    "fragment_id": "chunk1",
                    "text": "Content 1" * 50,
                    "metadata": {},
                },
                {
                    "fragment_id": "chunk2",
                    "text": "Content 2" * 50,
                    "metadata": {},
                },
            ]
        }
        mock_client.inspect_knowledge_graph.return_value = {
            "nodes": 100,
            "edges": 500,
        }

        original_callback = cli.callback

        def new_callback(*args, **kwargs):
            ctx = click.get_current_context()
            ctx.obj = mock_client
            return original_callback(*args, **kwargs)

        cli.callback = new_callback

        yield mock_client

        cli.callback = original_callback


def test_analytics(runner, mock_r2r_client):
    filters = {"date": "2023-01-01"}
    analysis_types = {"type": "user_activity"}

    result = runner.invoke(
        cli,
        [
            "analytics",
            "--filters",
            json.dumps(filters),
            "--analysis-types",
            json.dumps(analysis_types),
        ],
    )

    assert result.exit_code == 0
    assert "success" in result.output
    mock_r2r_client.analytics.assert_called_once_with(filters, analysis_types)


def test_analytics_invalid_json(runner, mock_r2r_client):
    result = runner.invoke(
        cli,
        [
            "analytics",
            "--filters",
            "invalid_json",
            "--analysis-types",
            '{"type": "user_activity"}',
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--filters'" in result.output


def test_app_settings(runner, mock_r2r_client):
    result = runner.invoke(cli, ["app-settings"])

    assert result.exit_code == 0
    assert "setting1" in result.output
    assert "value2" in result.output
    mock_r2r_client.app_settings.assert_called_once()


def test_users_overview(runner, mock_r2r_client):
    result = runner.invoke(cli, ["users-overview", "--user-ids", "user1"])

    assert result.exit_code == 0
    assert "Time taken:" in result.output
    mock_r2r_client.users_overview.assert_called_once_with(
        ["user1"], None, None
    )


def test_users_overview_no_ids(runner, mock_r2r_client):
    result = runner.invoke(cli, ["users-overview"])

    assert result.exit_code == 0
    assert "Time taken:" in result.output
    mock_r2r_client.users_overview.assert_called_once_with(None, None, None)


def test_delete(runner, mock_r2r_client):
    result = runner.invoke(
        cli, ["delete", "-f", "date:gt:2023-01-01", "-f", "status:eq:inactive"]
    )

    assert result.exit_code == 0
    assert "deleted" in result.output
    expected_filters = {
        "date": {"$gt": "2023-01-01"},
        "status": {"$eq": "inactive"},
    }
    mock_r2r_client.delete.assert_called_once_with(filters=expected_filters)


def test_delete_invalid_filter(runner, mock_r2r_client):
    result = runner.invoke(cli, ["delete", "-f", "invalid_filter"])

    assert result.exit_code != 0


def test_documents_overview_without_document_id(runner, mock_r2r_client):
    result = runner.invoke(
        cli,
        [
            "documents-overview",
        ],
    )

    assert result.exit_code == 0
    mock_r2r_client.documents_overview.assert_called_once()


def test_documents_overview_with_document_id(runner, mock_r2r_client):
    result = runner.invoke(
        cli, ["documents-overview", "--document-ids", "doc1"]
    )

    assert result.exit_code == 0
    assert "doc1" in result.output
    mock_r2r_client.documents_overview.assert_called_once_with(
        ["doc1"], None, None
    )


def test_document_chunks(runner, mock_r2r_client):
    result = runner.invoke(cli, ["document-chunks", "--document-id", "doc1"])

    assert result.exit_code == 0
    assert "Number of chunks: 2" in result.output
    assert "Fragment ID: chunk1" in result.output
    assert "Text: Content 1" in result.output
    assert "Content 1" * 5 in result.output
    assert "..." in result.output
    assert "Fragment ID: chunk2" in result.output
    assert "Text: Content 2" in result.output
    mock_r2r_client.document_chunks.assert_called_once_with("doc1", None, None)


def test_document_chunks_no_id(runner, mock_r2r_client):
    result = runner.invoke(cli, ["document-chunks"])

    assert result.exit_code == 0
    assert "Error: Document ID is required." in result.output


def test_inspect_knowledge_graph_no_kg_provider_specified(
    runner, mock_r2r_client
):
    result = runner.invoke(cli, ["inspect-knowledge-graph", "--limit", "100"])

    assert result.exit_code == 1
    mock_r2r_client.inspect_knowledge_graph.assert_called_once_with(
        None, "100"
    )


def test_inspect_knowledge_graph_no_limit_no_kg_provider_specified(
    runner, mock_r2r_client
):
    result = runner.invoke(cli, ["inspect-knowledge-graph"])

    assert result.exit_code == 1
    mock_r2r_client.inspect_knowledge_graph.assert_called_once_with(None, None)
