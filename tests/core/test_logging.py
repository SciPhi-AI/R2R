import logging
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from r2r.core import (
    LocalPipeLoggingProvider,
    LoggingConfig,
    PostgresLoggingConfig,
    PostgresPipeLoggingProvider,
)
from r2r.core.utils import generate_run_id

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def local_provider():
    """Fixture to create and tear down the LocalPipeLoggingProvider with a unique database file."""
    # Generate a unique file name for the SQLite database
    unique_id = str(uuid.uuid4())
    logging_path = f"test_{unique_id}.sqlite"

    # Setup the LocalPipeLoggingProvider with the unique file
    provider = LocalPipeLoggingProvider(LoggingConfig(logging_path=logging_path))
    
    # Provide the setup provider to the test
    yield provider

    # Cleanup: Remove the SQLite file after test completes
    provider.close()
    if os.path.exists(logging_path):
        os.remove(logging_path)

@pytest.mark.asyncio
async def test_local_logging(local_provider):
    """Test logging and retrieving from the local logging provider."""
    run_id = generate_run_id()
    await local_provider.init()
    await local_provider.log(run_id, "key", "value")
    logs = await local_provider.get_logs([run_id])
    assert len(logs) == 1
    assert logs[0]["key"] == "key"
    assert logs[0]["value"] == "value"

@pytest.mark.asyncio
async def test_multiple_log_entries(local_provider):
    """Test logging multiple entries and retrieving them."""
    run_id_0 = generate_run_id()
    run_id_1 = generate_run_id()
    run_id_2 = generate_run_id()
    await local_provider.init()

    entries = [
        (run_id_0, "key_0", "value_0"),
        (run_id_1, "key_1", "value_1"),
        (run_id_2, "key_2", "value_2")
    ]
    for run_id, key, value in entries:
        await local_provider.log(run_id, key, value)

    logs = await local_provider.get_logs([run_id_0, run_id_1, run_id_2])
    assert len(logs) == 3
    
    # Check that logs are returned in the correct order (most recent first if applicable)
    for log in logs:
        selected_entry = [entry for entry in entries if entry[0] == log["pipe_run_id"]][0]
        assert log["pipe_run_id"] == selected_entry[0]
        assert log["key"] == selected_entry[1]
        assert log["value"] == selected_entry[2]

@pytest.mark.asyncio
async def test_log_retrieval_limit(local_provider):
    """Test the max_logs limit parameter works correctly."""
    await local_provider.init()

    run_ids = []
    for i in range(10):  # Add 10 entries
        run_ids.append(generate_run_id())
        await local_provider.log(
            run_ids[-1], f"key_{i}", f"value_{i}"
        )

    logs = await local_provider.get_logs(run_ids[0:5])
    assert len(logs) == 5  # Ensure only 5 logs are returned

@pytest.mark.asyncio
async def test_specific_run_type_retrieval(local_provider):
    """Test retrieving logs for a specific run type works correctly."""
    await local_provider.init()
    run_id_0 = generate_run_id()
    run_id_1 = generate_run_id()

    await local_provider.log(run_id_0, "pipeline_type", "search", is_pipeline_info=True)
    await local_provider.log(run_id_0, "key_0", "value_0")
    await local_provider.log(run_id_1, "pipeline_type", "rag", is_pipeline_info=True)
    await local_provider.log(run_id_1, "key_1", "value_1")
    
    run_ids = await local_provider.get_run_ids("search")
    logs = await local_provider.get_logs(run_ids)
    assert len(logs) == 1
    assert logs[0]["pipe_run_id"] == run_id_0
    assert logs[0]["key"] == "key_0"
    assert logs[0]["value"] == "value_0"

@pytest.fixture(scope="function")
def postgres_provider():
    """Fixture to create and tear down the PostgresPipeLoggingProvider."""
    log_table = f"logs_{str(uuid.uuid4()).replace('-', '_')}"
    log_info_table =  f"log_info_{str(uuid.uuid4()).replace('-', '_')}"

    provider = PostgresPipeLoggingProvider(PostgresLoggingConfig(log_table=log_table, log_info_table=log_info_table))
    yield provider

@pytest.mark.asyncio
async def test_postgres_logging(postgres_provider):
    """Test logging and retrieving from the postgres logging provider."""
    await postgres_provider.init()
    run_id = generate_run_id()
    await postgres_provider.log(run_id, "key", "value")
    logs = await postgres_provider.get_logs([run_id])
    assert len(logs) == 1
    assert logs[0]["key"] == "key"
    assert logs[0]["value"] == "value"

@pytest.mark.asyncio
async def test_postgres_multiple_log_entries(postgres_provider):
    """Test logging multiple entries and retrieving them."""
    await postgres_provider.init()
    run_id_0 = generate_run_id()
    run_id_1 = generate_run_id()
    run_id_2 = generate_run_id()

    entries = [
        (run_id_0, "key_0", "value_0"),
        (run_id_1, "key_1", "value_1"),
        (run_id_2, "key_2", "value_2")
    ]
    for run_id, key, value in entries:
        await postgres_provider.log(run_id, key, value)

    logs = await postgres_provider.get_logs([run_id_0, run_id_1, run_id_2])
    assert len(logs) == 3
    
    # Check that logs are returned in the correct order (most recent first if applicable)
    for log in logs:
        selected_entry = [entry for entry in entries if entry[0] == log["pipe_run_id"]][0]
        assert log["pipe_run_id"] == selected_entry[0]
        assert log["key"] == selected_entry[1]
        assert log["value"] == selected_entry[2]

@pytest.mark.asyncio
async def test_postgres_log_retrieval_limit(postgres_provider):
    """Test the max_logs limit parameter works correctly."""
    await postgres_provider.init()
    run_ids = []
    for i in range(10):  # Add 10 entries
        run_ids.append(generate_run_id())
        await postgres_provider.log(
            run_ids[-1], f"key_{i}", f"value_{i}"
        )

    logs = await postgres_provider.get_logs(run_ids[:5])
    assert len(logs) == 5  # Ensure only 5 logs are returned

@pytest.mark.asyncio
async def test_postgres_specific_run_type_retrieval(postgres_provider):
    """Test retrieving logs for a specific run type works correctly."""
    await postgres_provider.init()
    run_id_0 = generate_run_id()
    run_id_1 = generate_run_id()

    await postgres_provider.log(run_id_0, "pipeline_type", "search", is_pipeline_info=True)
    await postgres_provider.log(run_id_0, "key_0", "value_0")
    await postgres_provider.log(run_id_1, "pipeline_type", "rag", is_pipeline_info=True)
    await postgres_provider.log(run_id_1, "key_1", "value_1")
    
    run_ids = await postgres_provider.get_run_ids("search")
    logs = await postgres_provider.get_logs(run_ids)
    assert len(logs) == 1
    assert logs[0]["pipe_run_id"] == run_id_0
    assert logs[0]["key"] == "key_0"
    assert logs[0]["value"] == "value_0"


