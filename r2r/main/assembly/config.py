import logging
import os
from enum import Enum
from typing import Any

import toml
from pydantic import BaseModel

from ...base.abstractions.agent import AgentConfig
from ...base.abstractions.document import DocumentType
from ...base.abstractions.llm import GenerationConfig
from ...base.logging.kv_logger import LoggingConfig
from ...base.providers.auth import AuthConfig
from ...base.providers.chunking import ChunkingConfig
from ...base.providers.crypto import CryptoConfig
from ...base.providers.database import DatabaseConfig, ProviderConfig
from ...base.providers.embedding import EmbeddingConfig
from ...base.providers.eval import EvalConfig
from ...base.providers.kg import KGConfig
from ...base.providers.llm import CompletionConfig
from ...base.providers.parsing import ParsingConfig
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
            "add_title_as_prefix",
        ],
        "eval": ["llm"],
        "kg": [
            "provider",
            "batch_size",
            "kg_extraction_config",
        ],
        "parsing": ["provider", "excluded_parsers"],
        "chunking": ["provider", "method"],
        "completion": ["provider"],
        "logging": ["provider", "log_table"],
        "prompt": ["provider"],
        "database": ["provider"],
        "agent": ["generation_config"],
    }
    auth: AuthConfig
    chunking: ChunkingConfig
    completion: CompletionConfig
    crypto: CryptoConfig
    database: DatabaseConfig
    embedding: EmbeddingConfig
    eval: EvalConfig
    kg: KGConfig
    logging: LoggingConfig
    parsing: ParsingConfig
    prompt: PromptConfig
    agent: AgentConfig

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
        self.completion = CompletionConfig.create(**self.completion)
        # override GenerationConfig defaults
        GenerationConfig.set_default(
            **self.completion.generation_config.dict()
        )

        self.auth = AuthConfig.create(**self.auth)
        self.chunking = ChunkingConfig.create(**self.chunking)
        self.crypto = CryptoConfig.create(**self.crypto)
        self.database = DatabaseConfig.create(**self.database)
        self.embedding = EmbeddingConfig.create(**self.embedding)
        self.eval = EvalConfig.create(**self.eval, llm=None)
        self.kg = KGConfig.create(**self.kg)
        self.logging = LoggingConfig.create(**self.logging)
        self.parsing = ParsingConfig.create(**self.parsing)
        self.prompt = PromptConfig.create(**self.prompt)
        self.agent = AgentConfig.create(**self.agent)

    def _validate_config_section(
        self, config_data: dict[str, Any], section: str, keys: list
    ):
        if section not in config_data:
            raise ValueError(f"Missing '{section}' section in config")
        if not all(key in config_data[section] for key in keys):
            raise ValueError(f"Missing required keys in '{section}' config")

    @classmethod
    def from_toml(cls, config_path: str = None) -> "R2RConfig":
        if config_path is None:
            # Get the root directory of the project
            file_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(file_dir, "..", "..", "..", "r2r.toml")

        # Load configuration from TOML file
        with open(config_path) as f:
            config_data = toml.load(f)

        return cls(config_data)

    def to_toml(self):
        config_data = {
            section: self._serialize_config(getattr(self, section))
            for section in R2RConfig.REQUIRED_KEYS.keys()
        }
        return toml.dumps(config_data)

    def save_to_redis(self, redis_client: Any, key: str):
        redis_client.set(f"R2RConfig:{key}", self.to_toml())

    @classmethod
    def load_from_redis(cls, redis_client: Any, key: str) -> "R2RConfig":
        config_data = redis_client.get(f"R2RConfig:{key}")
        if config_data is None:
            raise ValueError(
                f"Configuration not found in Redis with key '{key}'"
            )
        config_data = toml.loads(config_data)
        return cls(config_data)

    @classmethod
    def load_default_config(cls) -> dict:
        # Get the root directory of the project
        file_dir = os.path.dirname(os.path.abspath(__file__))
        default_config_path = os.path.join(
            file_dir, "..", "..", "..", "r2r.toml"
        )
        # Load default configuration from TOML file
        with open(default_config_path) as f:
            return toml.load(f)

    @staticmethod
    def _serialize_config(config_section: Any) -> dict:
        if isinstance(config_section, dict):
            return {
                R2RConfig._serialize_key(k): R2RConfig._serialize_config(v)
                for k, v in config_section.items()
            }
        elif isinstance(config_section, (list, tuple)):
            return [R2RConfig._serialize_config(item) for item in config_section]
        elif isinstance(config_section, Enum):
            return config_section.value
        elif isinstance(config_section, BaseModel):
            return R2RConfig._serialize_config(config_section.dict(exclude_none=True))
        else:
            return config_section
    
    @staticmethod
    def _serialize_key(key: Any) -> str:
        if isinstance(key, Enum):
            return key.value
        return str(key)
