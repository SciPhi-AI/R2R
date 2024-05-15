import json
import os
from typing import Any

from ..pipes.logging import LoggingConfig
from ..providers.embedding import EmbeddingConfig
from ..providers.eval import EvalConfig
from ..providers.llm import LLMConfig
from ..providers.prompt import PromptConfig
from ..providers.vector_db import VectorDBConfig


class R2RConfig:
    REQUIRED_KEYS: dict[str, list] = {
        "app": [],
        "embedding": [
            "provider",
            "search_model",
            "search_dimension",
            "batch_size",
            "text_splitter",
        ],
        "eval": [
            "provider",
            "sampling_fraction",
        ],
        "ingestion": [],
        "language_model": ["provider"],
        "logging": ["provider", "log_table"],
        "prompt": ["provider"],
        "vector_database": ["provider", "collection_name"],
    }

    def __init__(self, config_data: dict[str, Any]):
        # Load the default configuration
        default_config = self.load_default_config()

        # Override the default configuration with the passed configuration
        for key in config_data:
            if key in default_config:
                default_config[key].update(config_data[key])
            else:
                default_config[key] = config_data[key]

        # Validate and set the configuration
        for section, keys in R2RConfig.REQUIRED_KEYS.items():
            self._validate_config_section(default_config, section, keys)
            setattr(self, section, default_config[section])


        self.app = self.app # for type hinting
        self.embedding = EmbeddingConfig.create(**self.embedding)
        self.eval = EvalConfig.create(**self.eval)
        self.language_model = LLMConfig.create(**self.language_model)
        self.logging = LoggingConfig.create(**self.logging)
        self.prompt = PromptConfig.create(**self.prompt)
        self.vector_database = VectorDBConfig.create(**self.vector_database)

    def _validate_config_section(
        self, config_data: dict[str, Any], section: str, keys: list
    ):
        if section not in config_data:
            raise ValueError(f"Missing '{section}' section in config")
        if not all(key in config_data[section] for key in keys):
            raise ValueError(f"Missing required keys in '{section}' config")

    @classmethod
    def from_json(cls, config_path: str = None) -> "R2RConfig":
        if config_path is None:
            # Get the root directory of the project
            file_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(
                file_dir, "..", "..", "..", "config.json"
            )

        # Load configuration from JSON file
        with open(config_path) as f:
            config_data = json.load(f)

        return cls(config_data)

    # TODO - How to type 'redis.Redis' without introducing dependency on 'redis' package?
    def save_to_redis(self, redis_client: Any, key: str):
        config_data = {
            section: getattr(self, section)
            for section in R2RConfig.REQUIRED_KEYS.keys()
        }
        redis_client.set(f"R2RConfig:{key}", json.dumps(config_data))

    @classmethod
    def load_from_redis(cls, redis_client: Any, key: str) -> "R2RConfig":
        config_data = redis_client.get(f"R2RConfig:{key}")
        if config_data is None:
            raise ValueError(
                f"Configuration not found in Redis with key '{key}'"
            )
        return cls(json.loads(config_data))

    @classmethod
    def load_default_config(cls) -> dict:
        # Get the root directory of the project
        file_dir = os.path.dirname(os.path.abspath(__file__))
        default_config_path = os.path.join(
            file_dir, "..", "..", "..", "config.json"
        )
        # Load default configuration from JSON file
        with open(default_config_path) as f:
            return json.load(f)
