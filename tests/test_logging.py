import asyncio
import logging
import os
import uuid
from uuid import UUID

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
    await provider._init()
    yield provider
    await provider.close()
    if os.path.exists(logging_path):
        os.remove(logging_path)


@pytest.fixture(scope="function")
async def postgres_provider():
    log_table = f"logs_{str(uuid.uuid4()).replace('-', '_')}"
    log_info_table = f"log_info_{str(uuid.uuid4()).replace('-', '_')}"
    provider = PostgresKVLoggingProvider(
        PostgresLoggingConfig(
            log_table=log_table, log_info_table=log_info_table
        )
    )
    await provider._init()
    yield provider
    await provider.close()


@pytest.fixture
async def provider(request):
    return request.getfixturevalue(request.param)


all_providers = [
    pytest.param("local_provider", id="local"),
    pytest.param("postgres_provider", id="postgres"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", all_providers, indirect=True)
async def test_logging(provider):
    run_id = generate_run_id()
    await provider.log(run_id, "key", "value")
    logs = await provider.get_logs([run_id])
    assert len(logs) == 1
    assert logs[0]["key"] == "key"
    assert logs[0]["value"] == "value"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", all_providers, indirect=True)
async def test_multiple_log_entries(provider):
    run_ids = [generate_run_id() for _ in range(3)]
    entries = [
        (run_id, f"key_{i}", f"value_{i}") for i, run_id in enumerate(run_ids)
    ]
    for run_id, key, value in entries:
        await provider.log(run_id, key, value)

    logs = await provider.get_logs(run_ids)
    assert len(logs) == 3, f"Expected 3 logs, got {len(logs)}"

    for log in logs:
        log_id = log.get("log_id")
        assert log_id is not None, f"Log entry is missing 'log_id': {log}"

        if isinstance(log_id, str):
            log_id = UUID(log_id)

        matching_entries = [entry for entry in entries if entry[0] == log_id]
        assert (
            len(matching_entries) == 1
        ), f"No matching entry found for log_id {log_id}"

        selected_entry = matching_entries[0]
        assert log["key"] == selected_entry[1]
        assert log["value"] == selected_entry[2]

    # Additional check to ensure all entries were logged
    logged_ids = set(
        (
            UUID(log["log_id"])
            if isinstance(log["log_id"], str)
            else log["log_id"]
        )
        for log in logs
    )
    entry_ids = set(entry[0] for entry in entries)
    assert (
        logged_ids == entry_ids
    ), f"Mismatch between logged IDs {logged_ids} and entry IDs {entry_ids}"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", all_providers, indirect=True)
async def test_log_retrieval_limit(provider):
    run_ids = []
    for i in range(10):
        run_ids.append(generate_run_id())
        await provider.log(run_ids[-1], f"key_{i}", f"value_{i}")

    logs = await provider.get_logs(run_ids[:5])
    assert len(logs) == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", all_providers, indirect=True)
async def test_specific_run_type_retrieval(provider):
    run_id_0, run_id_1 = generate_run_id(), generate_run_id()

    await provider.log(run_id_0, "pipeline_type", "search")
    await provider.log(run_id_0, "key_0", "value_0")
    await provider.log(run_id_1, "pipeline_type", "rag")
    await provider.log(run_id_1, "key_1", "value_1")

    # Log info for both run IDs
    await provider.info_log(run_id_0, "search", uuid.uuid4())
    await provider.info_log(run_id_1, "rag", uuid.uuid4())

    run_info = await provider.get_info_logs(log_type_filter="search")
    assert len(run_info) == 1, f"Expected 1 'search' log, got {len(run_info)}"
    assert (
        run_info[0].run_id == run_id_0
    ), f"Expected run_id {run_id_0}, got {run_info[0].run_id}"

    logs = await provider.get_logs([run.run_id for run in run_info])
    assert len(logs) == 2, f"Expected 2 logs for run_id_0, got {len(logs)}"
    assert all(
        log["log_id"] == run_id_0 for log in logs
    ), "All logs should be for run_id_0"
    assert any(
        log["key"] == "pipeline_type" and log["value"] == "search"
        for log in logs
    ), "Should have a 'pipeline_type' log"
    assert any(
        log["key"] == "key_0" and log["value"] == "value_0" for log in logs
    ), "Should have a 'key_0' log"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", all_providers, indirect=True)
async def test_info_logging(provider):
    run_id = generate_run_id()
    user_id = uuid.uuid4()
    log_type = "search"
    await provider.info_log(run_id, log_type, user_id)
    info_logs = await provider.get_info_logs()
    assert len(info_logs) == 1
    assert info_logs[0].run_id == run_id
    assert info_logs[0].log_type == log_type
    assert info_logs[0].user_id == user_id


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", all_providers, indirect=True)
async def test_get_info_logs_with_user_filter(provider):
    user_id_1, user_id_2 = uuid.uuid4(), uuid.uuid4()
    await provider.info_log(generate_run_id(), "search", user_id_1)
    await provider.info_log(generate_run_id(), "rag", user_id_2)

    info_logs = await provider.get_info_logs(user_ids=[user_id_1])
    assert len(info_logs) == 1
    assert info_logs[0].user_id == user_id_1

    info_logs = await provider.get_info_logs(
        log_type_filter="rag", user_ids=[user_id_2]
    )
    assert len(info_logs) == 1
    assert info_logs[0].user_id == user_id_2
    assert info_logs[0].log_type == "rag"
