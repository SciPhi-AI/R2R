import asyncio
import logging
import os
import uuid

import pytest

from r2r import (
    LocalKVLoggingProvider,
    LoggingConfig,
    PostgresKVLoggingProvider,
    PostgresLoggingConfig,
    RedisKVLoggingProvider,
    RedisLoggingConfig,
    generate_run_id,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="function", autouse=True)
async def cleanup_tasks():
    yield
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture(scope="function")
async def local_provider():
    unique_id = str(uuid.uuid4())
    logging_path = f"test_{unique_id}.sqlite"
    provider = LocalKVLoggingProvider(LoggingConfig(logging_path=logging_path))
    await provider.init()
    yield provider
    await provider.close()
    if os.path.exists(logging_path):
        os.remove(logging_path)


@pytest.mark.asyncio
async def test_local_logging(local_provider):
    run_id = generate_run_id()
    await local_provider.log(run_id, "key", "value")
    logs = await local_provider.get_logs([run_id])
    assert len(logs) == 1
    assert logs[0]["key"] == "key"
    assert logs[0]["value"] == "value"


# FIXME: This test is causing Pytest to hang
# @pytest.mark.asyncio
# async def test_multiple_log_entries(local_provider):
#     """Test logging multiple entries and retrieving them."""
#     run_id_0 = generate_run_id()
#     run_id_1 = generate_run_id()
#     run_id_2 = generate_run_id()
#     await local_provider.init()

#     entries = [
#         (run_id_0, "key_0", "value_0"),
#         (run_id_1, "key_1", "value_1"),
#         (run_id_2, "key_2", "value_2"),
#     ]
#     for run_id, key, value in entries:
#         await local_provider.log(run_id, key, value)

#     logs = await local_provider.get_logs([run_id_0, run_id_1, run_id_2])
#     assert len(logs) == 3

#     # Check that logs are returned in the correct order (most recent first if applicable)
#     for log in logs:
#         selected_entry = [
#             entry for entry in entries if entry[0] == log["log_id"]
#         ][0]
#         assert log["log_id"] == selected_entry[0]
#         assert log["key"] == selected_entry[1]
#         assert log["value"] == selected_entry[2]


# FIXME: This test is causing Pytest to hang
# @pytest.mark.asyncio
# async def test_log_retrieval_limit(local_provider):
#     """Test the max_logs limit parameter works correctly."""
#     await local_provider.init()

#     run_ids = []
#     for i in range(10):  # Add 10 entries
#         run_ids.append(generate_run_id())
#         await local_provider.log(run_ids[-1], f"key_{i}", f"value_{i}")

#     logs = await local_provider.get_logs(run_ids[:5])
#     assert len(logs) == 5  # Ensure only 5 logs are returned


# FIXME: This test is causing Pytest to hang
# @pytest.mark.asyncio
# async def test_specific_run_type_retrieval(local_provider):
#     """Test retrieving logs for a specific run type works correctly."""
#     await local_provider.init()
#     run_id_0 = generate_run_id()
#     run_id_1 = generate_run_id()

#     await local_provider.log(
#         run_id_0, "pipeline_type", "search", is_info_log=True
#     )
#     await local_provider.log(run_id_0, "key_0", "value_0")
#     await local_provider.log(
#         run_id_1, "pipeline_type", "rag", is_info_log=True
#     )
#     await local_provider.log(run_id_1, "key_1", "value_1")

#     run_info = await local_provider.get_run_info(log_type_filter="search")
#     logs = await local_provider.get_logs([run.run_id for run in run_info])
#     assert len(logs) == 1
#     assert logs[0]["log_id"] == run_id_0
#     assert logs[0]["key"] == "key_0"
#     assert logs[0]["value"] == "value_0"


@pytest.fixture(scope="function")
async def postgres_provider():
    log_table = f"logs_{str(uuid.uuid4()).replace('-', '_')}"
    log_info_table = f"log_info_{str(uuid.uuid4()).replace('-', '_')}"
    provider = PostgresKVLoggingProvider(
        PostgresLoggingConfig(
            log_table=log_table, log_info_table=log_info_table
        )
    )
    await provider.init()
    yield provider
    await provider.close()


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
        (run_id_2, "key_2", "value_2"),
    ]
    for run_id, key, value in entries:
        await postgres_provider.log(run_id, key, value)

    logs = await postgres_provider.get_logs([run_id_0, run_id_1, run_id_2])
    assert len(logs) == 3

    # Check that logs are returned in the correct order (most recent first if applicable)
    for log in logs:
        selected_entry = [
            entry for entry in entries if entry[0] == log["log_id"]
        ][0]
        assert log["log_id"] == selected_entry[0]
        assert log["key"] == selected_entry[1]
        assert log["value"] == selected_entry[2]


@pytest.mark.asyncio
async def test_postgres_log_retrieval_limit(postgres_provider):
    """Test the max_logs limit parameter works correctly."""
    await postgres_provider.init()
    run_ids = []
    for i in range(10):  # Add 10 entries
        run_ids.append(generate_run_id())
        await postgres_provider.log(run_ids[-1], f"key_{i}", f"value_{i}")

    logs = await postgres_provider.get_logs(run_ids[:5])
    assert len(logs) == 5  # Ensure only 5 logs are returned


@pytest.mark.asyncio
async def test_postgres_specific_run_type_retrieval(postgres_provider):
    """Test retrieving logs for a specific run type works correctly."""
    await postgres_provider.init()
    run_id_0 = generate_run_id()
    run_id_1 = generate_run_id()

    await postgres_provider.log(
        run_id_0, "pipeline_type", "search", is_info_log=True
    )
    await postgres_provider.log(run_id_0, "key_0", "value_0")
    await postgres_provider.log(
        run_id_1, "pipeline_type", "rag", is_info_log=True
    )
    await postgres_provider.log(run_id_1, "key_1", "value_1")

    run_info = await postgres_provider.get_run_info(log_type_filter="search")
    logs = await postgres_provider.get_logs([run.run_id for run in run_info])
    assert len(logs) == 1
    assert logs[0]["log_id"] == run_id_0
    assert logs[0]["key"] == "key_0"
    assert logs[0]["value"] == "value_0"


# @pytest.fixture(scope="function")
# async def redis_provider():
#     log_table = f"logs_{str(uuid.uuid4()).replace('-', '_')}"
#     log_info_table = f"log_info_{str(uuid.uuid4()).replace('-', '_')}"
#     provider = RedisKVLoggingProvider(
#         RedisLoggingConfig(log_table=log_table, log_info_table=log_info_table)
#     )
#     await provider.init()
#     yield provider
#     await provider.close()


# @pytest.mark.asyncio
# async def test_redis_logging(redis_provider):
#     """Test logging and retrieving from the Redis logging provider."""
#     run_id = generate_run_id()
#     await redis_provider.log(run_id, "key", "value")
#     logs = await redis_provider.get_logs([run_id])
#     assert len(logs) == 1
#     assert logs[0]["key"] == "key"
#     assert logs[0]["value"] == "value"


# @pytest.mark.asyncio
# async def test_redis_multiple_log_entries(redis_provider):
#     """Test logging multiple entries and retrieving them."""
#     run_id_0 = generate_run_id()
#     run_id_1 = generate_run_id()
#     run_id_2 = generate_run_id()

#     entries = [
#         (run_id_0, "key_0", "value_0"),
#         (run_id_1, "key_1", "value_1"),
#         (run_id_2, "key_2", "value_2"),
#     ]
#     for run_id, key, value in entries:
#         await redis_provider.log(run_id, key, value)

#     logs = await redis_provider.get_logs([run_id_0, run_id_1, run_id_2])
#     assert len(logs) == 3

#     # Check that logs are returned in the correct order (most recent first if applicable)
#     for log in logs:
#         selected_entry = [
#             entry for entry in entries if entry[0] == log["log_id"]
#         ][0]
#         assert log["log_id"] == selected_entry[0]
#         assert log["key"] == selected_entry[1]
#         assert log["value"] == selected_entry[2]


# @pytest.mark.asyncio
# async def test_redis_log_retrieval_limit(redis_provider):
#     """Test the max_logs limit parameter works correctly."""
#     run_ids = []
#     for i in range(10):  # Add 10 entries
#         run_ids.append(generate_run_id())
#         await redis_provider.log(run_ids[-1], f"key_{i}", f"value_{i}")

#     logs = await redis_provider.get_logs(run_ids[:5])
#     assert len(logs) == 5  # Ensure only 5 logs are returned


# @pytest.mark.asyncio
# async def test_redis_specific_run_type_retrieval(redis_provider):
#     """Test retrieving logs for a specific run type works correctly."""
#     run_id_0 = generate_run_id()
#     run_id_1 = generate_run_id()

#     await redis_provider.log(
#         run_id_0, "pipeline_type", "search", is_info_log=True
#     )
#     await redis_provider.log(run_id_0, "key_0", "value_0")
#     await redis_provider.log(
#         run_id_1, "pipeline_type", "rag", is_info_log=True
#     )
#     await redis_provider.log(run_id_1, "key_1", "value_1")

#     run_info = await redis_provider.get_run_info(log_type_filter="search")
#     logs = await redis_provider.get_logs([run.run_id for run in run_info])
#     assert len(logs) == 1
#     assert logs[0]["log_id"] == run_id_0
#     assert logs[0]["key"] == "key_0"
#     assert logs[0]["value"] == "value_0"
