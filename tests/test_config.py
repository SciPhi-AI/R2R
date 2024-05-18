import json
from unittest.mock import mock_open, patch

import pytest


@pytest.fixture
def mock_file():
    # Prepare the JSON data as a string
    mock_data = json.dumps(
        {
            "app": {},
            "embedding": {
                "provider": "example_provider",
                "search_model": "model",
                "search_dimension": 128,
                "batch_size": 16,
                "text_splitter": "default",
            },
            "eval": {"provider": "eval_provider", "sampling_fraction": 0.1},
            "ingestion": {},
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

    # Use `patch` to replace the built-in open function with mock_open
    with patch("builtins.open", mock_open(read_data=mock_data)) as m:
        yield m


@pytest.mark.asyncio
def test_r2r_config_loading_required_keys(mock_file):
    from r2r.core import R2RConfig

    # Assuming R2RConfig.from_json tries to open "config.json"
    config = R2RConfig.from_json("config.json")
    assert (
        config.embedding.provider == "example_provider"
    ), "Provider should match the mock data"
