import logging
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from r2r.core import LocalPipeLoggingProvider  # , PostgresPipeLoggingProvider

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def set_env_vars():
    os.environ["POSTGRES_DBNAME"] = "test_db"
    os.environ["POSTGRES_USER"] = "user"
    os.environ["POSTGRES_PASSWORD"] = "password"
    os.environ["POSTGRES_HOST"] = "localhost"
    os.environ["POSTGRES_PORT"] = "5432"
    yield

    # Optionally clear the environment variables after tests are done
    os.environ.pop("POSTGRES_DBNAME", None)
    os.environ.pop("POSTGRES_USER", None)
    os.environ.pop("POSTGRES_PASSWORD", None)
    os.environ.pop("POSTGRES_HOST", None)
    os.environ.pop("POSTGRES_PORT", None)


# @pytest.fixture
# def postgres_provider():
#     """Fixture to create and tear down the PostgresPipeLoggingProvider."""
#     with patch("psycopg2.connect") as mock_connect:
#         # Create a mock connection object
#         mock_connect.return_value = MagicMock()
#         yield PostgresPipeLoggingProvider(collection_name="test_logs")


# def test_log_entry(postgres_provider):
#     """Test that logging an entry works correctly."""
#     with patch.object(postgres_provider, "conn") as mock_conn:
#         mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
#         postgres_provider.log("uuid", "ingestion", "method", "result", "INFO")
#         mock_cursor.execute.assert_called_once_with(
#             "INSERT INTO test_logs (timestamp, pipe_run_id, pipe_run_type, method, result, log_level) VALUES (NOW(), %s, %s, %s, %s, %s)",
#             ("uuid", "ingestion", "method", "result", "INFO"),
#         )


# def test_get_logs(postgres_provider):
#     """Test retrieving logs works correctly and handles no logs case."""
#     with patch.object(postgres_provider, "conn") as mock_conn:
#         mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
#         mock_cursor.description = [
#             ("timestamp",),
#             ("pipe_run_id",),
#             ("pipe_run_type",),
#             ("method",),
#             ("result",),
#             ("log_level",),
#         ]
#         mock_cursor.fetchall.return_value = [
#             (
#                 "2021-01-01 00:00:00",
#                 "uuid-1",
#                 "ingestion",
#                 "initialize",
#                 "success",
#                 "INFO",
#             ),
#         ]
#         logs = postgres_provider.get_logs(10)
#         assert len(logs) == 1
#         assert logs[0]["result"] == "success"


# def test_close(postgres_provider):
#     """Test that the close method properly closes the connection."""
#     with patch.object(postgres_provider, "conn") as mock_conn:
#         postgres_provider.close()
#         mock_conn.close.assert_called_once()


# def test_log_entry_with_exception(postgres_provider):
#     """Test error handling when logging an entry fails."""
#     with patch.object(postgres_provider, "conn") as mock_conn:
#         mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
#         mock_cursor.execute.side_effect = Exception("Database Error")
#         postgres_provider.log(
#             "uuid", "ingestion", "method", "error_result", "ERROR"
#         )


# def test_get_logs_specific_run_type(postgres_provider):
#     """Test retrieving logs for a specific run type."""
#     with patch.object(postgres_provider, "conn") as mock_conn:
#         mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
#         mock_cursor.description = [
#             ("timestamp",),
#             ("pipe_run_id",),
#             ("pipe_run_type",),
#             ("method",),
#             ("result",),
#             ("log_level",),
#         ]
#         mock_cursor.fetchall.return_value = [
#             (
#                 "2021-01-01 00:00:00",
#                 "uuid-2",
#                 "embedding",
#                 "process",
#                 "completed",
#                 "INFO",
#             ),
#         ]
#         logs = postgres_provider.get_logs(10, "embedding")
#         assert len(logs) == 1
#         assert logs[0]["pipe_run_type"] == "embedding"


# def test_get_no_logs(postgres_provider):
#     """Test retrieving logs when there are no logs available."""
#     with patch.object(postgres_provider, "conn") as mock_conn:
#         mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
#         mock_cursor.description = [
#             ("timestamp",),
#             ("pipe_run_id",),
#             ("pipe_run_type",),
#             ("method",),
#             ("result",),
#             ("log_level",),
#         ]
#         mock_cursor.fetchall.return_value = []
#         logs = postgres_provider.get_logs(10)
#         assert len(logs) == 0


# def test_logging_and_retrieving_integration(postgres_provider):
#     """Integration test to log and then retrieve logs."""
#     # Log some entries
#     postgres_provider.log("uuid1", "ingestion", "init", "init_success", "INFO")
#     postgres_provider.log(
#         "uuid2", "evaluation", "evaluate", "eval_success", "INFO"
#     )
#     # Retrieve and verify
#     with patch.object(postgres_provider, "conn") as mock_conn:
#         mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
#         mock_cursor.description = [
#             ("timestamp",),
#             ("pipe_run_id",),
#             ("pipe_run_type",),
#             ("method",),
#             ("result",),
#             ("log_level",),
#         ]
#         mock_cursor.fetchall.return_value = [
#             (
#                 "2021-01-01 00:00:00",
#                 "uuid1",
#                 "ingestion",
#                 "init",
#                 "init_success",
#                 "INFO",
#             ),
#             (
#                 "2021-01-01 00:01:00",
#                 "uuid2",
#                 "evaluation",
#                 "evaluate",
#                 "eval_success",
#                 "INFO",
#             ),
#         ]
#         logs = postgres_provider.get_logs(10)
#         assert len(logs) == 2
#         assert logs[0]["result"] == "init_success"
#         assert logs[1]["result"] == "eval_success"


@pytest.fixture
def local_provider():
    """Fixture to create and tear down the LocalPipeLoggingProvider with a unique database file."""
    # Generate a unique file name for the SQLite database
    unique_id = str(uuid.uuid4())
    db_path = f"test_{unique_id}.sqlite"

    # Setup the LocalPipeLoggingProvider with the unique file
    provider = LocalPipeLoggingProvider(
        collection_name="test_logs", logging_path=db_path
    )

    # Provide the setup provider to the test
    yield provider

    # Cleanup: Remove the SQLite file after test completes
    provider.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_local_logging(local_provider):
    """Test logging and retrieving from the local logging provider."""
    local_provider.log("uuid", "ingestion", "method", "result", "INFO")
    logs = local_provider.get_logs(10)
    assert len(logs) == 1
    assert logs[0]["result"] == "result"
    assert logs[0]["pipe_run_type"] == "ingestion"
    assert logs[0]["method"] == "method"
    assert logs[0]["log_level"] == "INFO"


def test_multiple_log_entries(local_provider):
    """Test logging multiple entries and retrieving them."""
    entries = [
        ("uuid1", "ingestion", "init", "success", "INFO"),
        ("uuid2", "search", "query", "results", "INFO"),
        ("uuid3", "evaluation", "analyze", "metrics", "INFO"),
    ]
    for uuid, type, method, result, level in entries:
        local_provider.log(uuid, type, method, result, level)

    logs = local_provider.get_logs(10)
    assert len(logs) == 3
    # Check that logs are returned in the correct order (most recent first if applicable)
    for log, entry in zip(logs, entries):
        assert log["pipe_run_id"] == entry[0]
        assert log["pipe_run_type"] == entry[1]
        assert log["method"] == entry[2]
        assert log["result"] == entry[3]
        assert log["log_level"] == entry[4]


def test_log_retrieval_limit(local_provider):
    """Test the max_logs limit parameter works correctly."""
    for i in range(10):  # Add 10 entries
        local_provider.log(
            f"uuid{i}", "ingestion", "method", f"result{i}", "INFO"
        )

    logs = local_provider.get_logs(5)
    assert len(logs) == 5  # Ensure only 5 logs are returned


def test_specific_run_type_retrieval(local_provider):
    """Test retrieving logs for a specific run type works correctly."""
    local_provider.log("uuid1", "ingestion", "init", "success", "INFO")
    local_provider.log("uuid2", "search", "query", "results", "INFO")
    logs = local_provider.get_logs(10, "search")
    assert len(logs) == 1
    assert logs[0]["pipe_run_id"] == "uuid2"
    assert logs[0]["pipe_run_type"] == "search"
