import json
import logging
import os
from enum import Enum
from typing import Any

from ...base.abstractions.document import DocumentType
from ...base.abstractions.llm import GenerationConfig
from ...base.logging.kv_logger import LoggingConfig
from ...base.providers.auth import AuthConfig
from ...base.providers.crypto import CryptoConfig
from ...base.providers.database import DatabaseConfig, ProviderConfig
from ...base.providers.embedding import EmbeddingConfig
from ...base.providers.eval import EvalConfig
from ...base.providers.kg import KGConfig
from ...base.providers.llm import LLMConfig
from ...base.providers.prompt import PromptConfig

logger = logging.getLogger(__name__)


class R2RConfig:
    REQUIRED_KEYS: dict[str, list] = {
        "crypto": ["provider"],
        "auth": ["provider"],
        "embedding": [
            "provider",
            "base_model",
            "base_dimension",
            "batch_size",
            "text_splitter",
            "add_title_as_prefix",
        ],
        "eval": ["llm"],
        "kg": [
            "provider",
            "batch_size",
            "kg_extraction_config",
            "text_splitter",
        ],
        "ingestion": ["excluded_parsers"],
        "completions": ["provider"],
        "logging": ["provider", "log_table"],
        "prompt": ["provider"],
        "database": ["provider"],
    }
    auth: AuthConfig
    crypto: CryptoConfig
    embedding: EmbeddingConfig
    kg: KGConfig
    completions: LLMConfig
    logging: LoggingConfig
    prompt: PromptConfig
    database: DatabaseConfig

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
            # Check the keys when provider is set
            # TODO - Clean up robust null checks
            if "provider" in default_config[section] and (
                default_config[section]["provider"] is not None
                and default_config[section]["provider"] != "None"
                and default_config[section]["provider"] != "null"
            ):
                self._validate_config_section(default_config, section, keys)
            setattr(self, section, default_config[section])
        self.auth = AuthConfig.create(**self.auth)
        self.crypto = CryptoConfig.create(**self.crypto)
        self.ingestion = self.ingestion  # for type hinting
        self.ingestion["excluded_parsers"] = [
            DocumentType(k) for k in self.ingestion["excluded_parsers"]
        ]
        # override GenerationConfig defaults
        GenerationConfig.set_default(
            **self.completions.get("generation_config", {})
        )
        self.embedding = EmbeddingConfig.create(**self.embedding)
        self.kg = KGConfig.create(**self.kg)
        eval_llm = self.eval.pop("llm", None)
        self.eval = EvalConfig.create(
            **self.eval, llm=LLMConfig.create(**eval_llm) if eval_llm else None
        )
        self.completions = LLMConfig.create(**self.completions)
        self.logging = LoggingConfig.create(**self.logging)
        self.prompt = PromptConfig.create(**self.prompt)
        self.database = DatabaseConfig.create(**self.database)

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
            config_path = os.path.join(file_dir, "..", "..", "..", "r2r.json")

        # Load configuration from JSON file
        with open(config_path) as f:
            config_data = json.load(f)

        return cls(config_data)

    def to_json(self):
        config_data = {
            section: self._serialize_config(getattr(self, section))
            for section in R2RConfig.REQUIRED_KEYS.keys()
        }
        return json.dumps(config_data)

    def save_to_redis(self, redis_client: Any, key: str):
        redis_client.set(f"R2RConfig:{key}", self.to_json())

    @classmethod
    def load_from_redis(cls, redis_client: Any, key: str) -> "R2RConfig":
        config_data = redis_client.get(f"R2RConfig:{key}")
        if config_data is None:
            raise ValueError(
                f"Configuration not found in Redis with key '{key}'"
            )
        config_data = json.loads(config_data)
        return cls(config_data)

    @classmethod
    def load_default_config(cls) -> dict:
        # Get the root directory of the project
        file_dir = os.path.dirname(os.path.abspath(__file__))
        default_config_path = os.path.join(
            file_dir, "..", "..", "..", "r2r.json"
        )
        # Load default configuration from JSON file
        with open(default_config_path) as f:
            return json.load(f)

    @staticmethod
    def _serialize_config(config_section: Any) -> dict:
        # TODO - Make this approach cleaner
        if isinstance(config_section, ProviderConfig):
            config_section = config_section.dict()
        filtered_result = {}
        for k, v in config_section.items():
            if isinstance(k, Enum):
                k = k.value
            if isinstance(v, dict):
                formatted_v = {
                    k2.value if isinstance(k2, Enum) else k2: v2
                    for k2, v2 in v.items()
                }
                v = formatted_v
            filtered_result[k] = v
        return filtered_result
