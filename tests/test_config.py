import json
from unittest.mock import mock_open, patch, Mock
import pytest
from r2r import R2RConfig, DocumentType


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
                "search_model": "model",
                "search_dimension": 128,
                "batch_size": 16,
                "text_splitter": "default",
            },
            "eval": {"llm": {"provider": "local"}},
            "ingestion": {"selected_parsers": {}},
            "completions": {"provider": "lm_provider"},
            "logging": {
                "provider": "local",
                "log_table": "logs",
                "log_info_table": "log_info",
            },
            "prompt": {"provider": "prompt_provider"},
            "vector_database": {
                "provider": "vector_db",
                "collection_name": "vectors",
            },
        }
    )
    with patch("builtins.open", mock_open(read_data=mock_data)) as m:
        yield m


@pytest.mark.asyncio
def test_r2r_config_loading_required_keys(mock_bad_file):
    with pytest.raises(ValueError):
        R2RConfig.from_json("config.json")


@pytest.mark.asyncio
def test_r2r_config_loading(mock_file):
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
            "search_model": "model",
            "search_dimension": 128,
            "batch_size": 16,
            "text_splitter": "default",
        },
        "eval": {"llm": {"provider": "local"}},
        "ingestion": {"selected_parsers": {"pdf": "default"}},
        "completions": {"provider": "lm_provider"},
        "logging": {
            "provider": "local",
            "log_table": "logs",
            "log_info_table": "log_info",
        },
        "prompt": {"provider": "prompt_provider"},
        "vector_database": {
            "provider": "vector_db",
            "collection_name": "vectors",
        },
    }
    mock_redis_client.get.return_value = json.dumps(config_data)
    config = R2RConfig.load_from_redis(mock_redis_client, "test_key")
    assert config.app["max_file_size_in_mb"] == 128
    assert config.ingestion["selected_parsers"][DocumentType.PDF] == "default"


def test_r2r_config_missing_section():
    invalid_data = {
        "embedding": {
            "provider": "example_provider",
            "search_model": "model",
            "search_dimension": 128,
            "batch_size": 16,
            "text_splitter": "default",
        }
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(invalid_data))):
        with pytest.raises(ValueError):
            R2RConfig.from_json("config.json")


def test_r2r_config_missing_required_key():
    invalid_data = {
        "app": {"max_file_size_in_mb": 128},
        "embedding": {
            "search_model": "model",
            "search_dimension": 128,
            "batch_size": 16,
            "text_splitter": "default",
        },
        "eval": {"llm": {"provider": "local"}},
        "ingestion": {"selected_parsers": {}},
        "completions": {"provider": "lm_provider"},
        "logging": {
            "provider": "local",
            "log_table": "logs",
            "log_info_table": "log_info",
        },
        "prompt": {"provider": "prompt_provider"},
        "vector_database": {
            "provider": "vector_db",
            "collection_name": "vectors",
        },
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(invalid_data))):
        with pytest.raises(ValueError):
            R2RConfig.from_json("config.json")
