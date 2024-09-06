import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import toml
from pydantic import BaseModel

from ..base.abstractions.llm import GenerationConfig
from ..base.agent.agent import AgentConfig
from ..base.logging.run_logger import LoggingConfig
from ..base.providers.auth import AuthConfig
from ..base.providers.chunking import ChunkingConfig
from ..base.providers.crypto import CryptoConfig
from ..base.providers.database import DatabaseConfig
from ..base.providers.embedding import EmbeddingConfig
from ..base.providers.file import FileConfig
from ..base.providers.kg import KGConfig
from ..base.providers.llm import CompletionConfig
from ..base.providers.parsing import ParsingConfig
from ..base.providers.prompt import PromptConfig

logger = logging.getLogger(__name__)


class R2RConfig:
    current_file_path = os.path.dirname(__file__)
    config_dir_root = os.path.join(current_file_path, "..", "configs")
    default_config_path = os.path.join(
        current_file_path, "..", "..", "r2r.toml"
    )

    CONFIG_OPTIONS = {}
    for file in os.listdir(config_dir_root):
        if file.endswith(".toml"):
            CONFIG_OPTIONS[file.removesuffix(".toml")] = os.path.join(
                config_dir_root, file
            )
    CONFIG_OPTIONS["default"] = None

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
        "kg": [
            "provider",
            "batch_size",
            "kg_enrichment_settings",
        ],
        "parsing": ["provider", "excluded_parsers"],
        "chunking": ["provider"],
        "completion": ["provider"],
        "logging": ["provider", "log_table"],
        "prompt": ["provider"],
        "database": ["provider"],
        "agent": ["generation_config"],
        "file": ["provider"],
    }
    auth: AuthConfig
    chunking: ChunkingConfig
    completion: CompletionConfig
    crypto: CryptoConfig
    database: DatabaseConfig
    embedding: EmbeddingConfig
    kg: KGConfig
    logging: LoggingConfig
    parsing: ParsingConfig
    prompt: PromptConfig
    agent: AgentConfig
    file: FileConfig

    def __init__(
        self, config_data: dict[str, Any], base_path: Optional[Path] = None
    ):
        """
        :param config_data: dictionary of configuration parameters
        :param base_path: base path when a relative path is specified for the prompts directory
        """
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
                if (
                    section == "prompt"
                    and "file_path" in default_config[section]
                    and not Path(
                        default_config[section]["file_path"]
                    ).is_absolute()
                    and base_path
                ):
                    # Make file_path absolute and relative to the base path
                    default_config[section]["file_path"] = str(
                        base_path / default_config[section]["file_path"]
                    )
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
        self.kg = KGConfig.create(**self.kg)
        self.logging = LoggingConfig.create(**self.logging)
        if "chunking_config" not in self.parsing:
            self.parsing["chunking_config"] = self.chunking
        self.parsing = ParsingConfig.create(**self.parsing)
        self.prompt = PromptConfig.create(**self.prompt)
        self.agent = AgentConfig.create(**self.agent)
        self.file = FileConfig.create(**self.file)

    def _validate_config_section(
        self, config_data: dict[str, Any], section: str, keys: list
    ):
        if section not in config_data:
            raise ValueError(f"Missing '{section}' section in config")
        if missing_keys := [
            key for key in keys if key not in config_data[section]
        ]:
            raise ValueError(
                f"Missing required keys in '{section}' config: {', '.join(missing_keys)}"
            )

    @classmethod
    def from_toml(cls, config_path: str = None) -> "R2RConfig":
        if config_path is None:
            config_path = R2RConfig.default_config_path

        # Load configuration from TOML file
        with open(config_path) as f:
            config_data = toml.load(f)

        return cls(config_data, base_path=Path(config_path).parent)

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
        with open(R2RConfig.default_config_path) as f:
            return toml.load(f)

    @staticmethod
    def _serialize_config(config_section: Any) -> dict:
        if isinstance(config_section, dict):
            return {
                R2RConfig._serialize_key(k): R2RConfig._serialize_config(v)
                for k, v in config_section.items()
            }
        elif isinstance(config_section, (list, tuple)):
            return [
                R2RConfig._serialize_config(item) for item in config_section
            ]
        elif isinstance(config_section, Enum):
            return config_section.value
        elif isinstance(config_section, BaseModel):
            return R2RConfig._serialize_config(
                config_section.model_dump(exclude_none=True)
            )
        else:
            return config_section

    @staticmethod
    def _serialize_key(key: Any) -> str:
        return key.value if isinstance(key, Enum) else str(key)

    @classmethod
    def load(
        cls,
        config_name: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> "R2RConfig":
        if config_path and config_name:
            raise ValueError("Cannot specify both config_path and config_name")

        if config_path := os.getenv("CONFIG_PATH") or config_path:
            return cls.from_toml(config_path)
        else:
            config_name = os.getenv("CONFIG_NAME") or config_name or "default"
            if config_name not in R2RConfig.CONFIG_OPTIONS:
                raise ValueError(f"Invalid config name: {config_name}")
            return cls.from_toml(R2RConfig.CONFIG_OPTIONS[config_name])
