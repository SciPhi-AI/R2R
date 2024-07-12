import asyncio
import json
from unittest.mock import Mock, mock_open, patch

import pytest

from r2r import DocumentType, R2RConfig


@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


@pytest.fixture(scope="session", autouse=True)
async def cleanup_tasks():
    yield
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.fixture
def mock_bad_file():
    mock_data = json.dumps({})
    with patch("builtins.open", mock_open(read_data=mock_data)) as m:
        yield m


@pytest.fixture
def mock_file():
    mock_data = json.dumps(
        {
            "app": {"max_file_size_in_mb": 128},
            "embedding": {
                "provider": "example_provider",
                "base_model": "model",
                "base_dimension": 128,
                "batch_size": 16,
                "text_splitter": "default",
            },
            "kg": {
                "provider": "None",
                "batch_size": 1,
                "text_splitter": {
                    "type": "recursive_character",
                    "chunk_size": 2048,
                    "chunk_overlap": 0,
                },
            },
            "eval": {"llm": {"provider": "local"}},
            "ingestion": {"excluded_parsers": {}},
            "completions": {"provider": "lm_provider"},
            "logging": {
                "provider": "local",
                "log_table": "logs",
                "log_info_table": "log_info",
            },
            "prompt": {"provider": "prompt_provider"},
            "database": {"provider": "vector_db"},
        }
    )
    with patch("builtins.open", mock_open(read_data=mock_data)) as m:
        yield m


@pytest.mark.asyncio
async def test_r2r_config_loading_required_keys(mock_bad_file):
    with pytest.raises(KeyError):
        R2RConfig.from_json("config.json")


@pytest.mark.asyncio
async def test_r2r_config_loading(mock_file):
    config = R2RConfig.from_json("config.json")
    assert (
        config.embedding.provider == "example_provider"
    ), "Provider should match the mock data"


@pytest.fixture
def mock_redis_client():
    client = Mock()
    return client


def test_r2r_config_serialization(mock_file, mock_redis_client):
    config = R2RConfig.from_json("config.json")
    config.save_to_redis(mock_redis_client, "test_key")
    mock_redis_client.set.assert_called_once()
    saved_data = json.loads(mock_redis_client.set.call_args[0][1])
    assert saved_data["app"]["max_file_size_in_mb"] == 128


def test_r2r_config_deserialization(mock_file, mock_redis_client):
    config_data = {
        "app": {"max_file_size_in_mb": 128},
        "embedding": {
            "provider": "example_provider",
            "base_model": "model",
            "base_dimension": 128,
            "batch_size": 16,
            "text_splitter": "default",
        },
        "kg": {
            "provider": "None",
            "batch_size": 1,
            "text_splitter": {
                "type": "recursive_character",
                "chunk_size": 2048,
                "chunk_overlap": 0,
            },
        },
        "eval": {"llm": {"provider": "local"}},
        "ingestion": {"excluded_parsers": ["pdf"]},
        "completions": {"provider": "lm_provider"},
        "logging": {
            "provider": "local",
            "log_table": "logs",
            "log_info_table": "log_info",
        },
        "prompt": {"provider": "prompt_provider"},
        "database": {"provider": "vector_db"},
    }
    mock_redis_client.get.return_value = json.dumps(config_data)
    config = R2RConfig.load_from_redis(mock_redis_client, "test_key")
    assert config.app["max_file_size_in_mb"] == 128
    assert DocumentType.PDF in config.ingestion["excluded_parsers"]


def test_r2r_config_missing_section():
    invalid_data = {
        "embedding": {
            "provider": "example_provider",
            "base_model": "model",
            "base_dimension": 128,
            "batch_size": 16,
            "text_splitter": "default",
        }
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(invalid_data))):
        with pytest.raises(KeyError):
            R2RConfig.from_json("config.json")


def test_r2r_config_missing_required_key():
    invalid_data = {
        "app": {"max_file_size_in_mb": 128},
        "embedding": {
            "base_model": "model",
            "base_dimension": 128,
            "batch_size": 16,
            "text_splitter": "default",
        },
        "kg": {
            "provider": "None",
            "batch_size": 1,
            "text_splitter": {
                "type": "recursive_character",
                "chunk_size": 2048,
                "chunk_overlap": 0,
            },
        },
        "completions": {"provider": "lm_provider"},
        "logging": {
            "provider": "local",
            "log_table": "logs",
            "log_info_table": "log_info",
        },
        "prompt": {"provider": "prompt_provider"},
        "database": {"provider": "vector_db"},
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(invalid_data))):
        with pytest.raises(KeyError):
            R2RConfig.from_json("config.json")
