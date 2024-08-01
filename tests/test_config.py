import asyncio
from unittest.mock import Mock, mock_open, patch

import pytest
import toml

from r2r import DocumentType, R2RConfig


@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="function", autouse=True)
async def cleanup_tasks():
    yield
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture(autouse=True)
async def manage_async_pipes():
    async_pipes = []
    yield async_pipes
    for pipe in async_pipes:
        await pipe.shutdown()


@pytest.fixture
def mock_bad_file():
    mock_data = toml.dumps({})
    with patch("builtins.open", mock_open(read_data=mock_data)) as m:
        yield m


@pytest.fixture
def mock_file():
    mock_data = toml.dumps(
        {
            "auth": {
                "provider": "r2r",
                "access_token_lifetime_in_minutes": 60,
                "refresh_token_lifetime_in_days": 7,
                "require_authentication": False,
                "require_email_verification": False,
                "default_admin_email": "admin@example.com",
                "default_admin_password": "change_me_immediately",
            },
            "completion": {
                "provider": "litellm",
                "concurrent_request_limit": 16,
                "generation_config": {
                    "model": "openai/gpt-4o",
                    "temperature": 0.1,
                    "top_p": 1,
                    "max_tokens_to_sample": 1024,
                    "stream": False,
                    "add_generation_kwargs": {},
                },
            },
            "crypto": {"provider": "bcrypt"},
            "database": {"provider": "postgres"},
            "parsing": {"provider": "r2r", "excluded_parsers": ["mp4"]},
            "chunking": {"provider": "r2r", "method": "recursive"},
            "embedding": {
                "provider": "litellm",
                "base_model": "text-embedding-3-small",
                "base_dimension": 512,
                "batch_size": 128,
                "add_title_as_prefix": False,
                "rerank_model": "None",
                "concurrent_request_limit": 256,
            },
            "eval": {"provider": "None"},
            "ingestion": {
                "excluded_parsers": ["mp4"],
                "override_parsers": [
                    {"document_type": "pdf", "parser": "PDFParser"}
                ],
                "text_splitter": {
                    "type": "recursive_character",
                    "chunk_size": 512,
                    "chunk_overlap": 20,
                },
            },
            "kg": {"provider": "None"},
            "logging": {
                "provider": "local",
                "log_table": "logs",
                "log_info_table": "log_info",
            },
            "prompt": {"provider": "r2r"},
        }
    )
    with patch("builtins.open", mock_open(read_data=mock_data)) as m:
        yield m


@pytest.mark.asyncio
async def test_r2r_config_loading_required_keys(mock_bad_file):
    with pytest.raises(KeyError):
        R2RConfig.from_toml("r2r.toml")


@pytest.mark.asyncio
async def test_r2r_config_loading(mock_file):
    try:
        config = R2RConfig.from_toml("r2r.toml")
        assert (
            config.embedding.provider == "litellm"
        ), "Provider should match the mock data"
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")


@pytest.fixture
def mock_redis_client():
    return Mock()


def test_r2r_config_serialization(mock_file, mock_redis_client):
    config = R2RConfig.from_toml("r2r.toml")
    config.save_to_redis(mock_redis_client, "test_key")
    mock_redis_client.set.assert_called_once()
    saved_data = toml.loads(mock_redis_client.set.call_args[0][1])
    assert saved_data["embedding"]["provider"] == "litellm"


def test_r2r_config_deserialization(mock_file, mock_redis_client):
    config_data = {
        "embedding": {
            "provider": "litellm",
            "base_model": "text-embedding-3-small",
            "base_dimension": 512,
            "batch_size": 128,
            "add_title_as_prefix": False,
            "rerank_model": "None",
            "concurrent_request_limit": 256,
        },
        "kg": {"provider": "None"},
        "eval": {"provider": "None"},
        "parsing": {"provider": "r2r"},
        "chunking": {"provider": "r2r"},
        "ingestion": {
            "excluded_parsers": ["mp4"],
            "override_parsers": [
                {"document_type": "pdf", "parser": "PDFParser"}
            ],
            "text_splitter": {
                "type": "recursive_character",
                "chunk_size": 512,
                "chunk_overlap": 20,
            },
        },
        "completion": {"provider": "litellm"},
        "logging": {
            "provider": "local",
            "log_table": "logs",
            "log_info_table": "log_info",
        },
        "prompt": {"provider": "r2r"},
        "database": {"provider": "postgres"},
    }
    mock_redis_client.get.return_value = toml.dumps(config_data)
    config = R2RConfig.load_from_redis(mock_redis_client, "test_key")
    assert DocumentType.MP4 in config.ingestion["excluded_parsers"]


def test_r2r_config_missing_section():
    invalid_data = {
        "embedding": {
            "provider": "litellm",
            "base_model": "text-embedding-3-small",
            "base_dimension": 512,
            "batch_size": 128,
            "add_title_as_prefix": False,
        }
    }
    with patch("builtins.open", mock_open(read_data=toml.dumps(invalid_data))):
        with pytest.raises(KeyError):
            R2RConfig.from_toml("r2r.toml")


def test_r2r_config_missing_required_key():
    invalid_data = {
        "auth": {"access_token_lifetime_in_minutes": 60},
        "embedding": {
            "base_model": "text-embedding-3-small",
            "base_dimension": 512,
            "batch_size": 128,
            "add_title_as_prefix": False,
        },
        "kg": {"provider": "None"},
        "completion": {"provider": "litellm"},
        "logging": {
            "provider": "local",
            "log_table": "logs",
            "log_info_table": "log_info",
        },
        "prompt": {"provider": "r2r"},
        "database": {"provider": "postgres"},
    }
    with patch("builtins.open", mock_open(read_data=toml.dumps(invalid_data))):
        with pytest.raises(KeyError):
            R2RConfig.from_toml("r2r.toml")
