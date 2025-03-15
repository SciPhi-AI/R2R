# FIXME: Once the agent is properly type annotated, remove the type: ignore comments
import logging
import os
from enum import Enum
from typing import Any, Optional

import toml
from pydantic import BaseModel

from ..base.abstractions import GenerationConfig
from ..base.agent.agent import RAGAgentConfig  # type: ignore
from ..base.providers import AppConfig
from ..base.providers.auth import AuthConfig
from ..base.providers.crypto import CryptoConfig
from ..base.providers.database import DatabaseConfig
from ..base.providers.email import EmailConfig
from ..base.providers.embedding import EmbeddingConfig
from ..base.providers.ingestion import IngestionConfig
from ..base.providers.llm import CompletionConfig
from ..base.providers.orchestration import OrchestrationConfig
from ..base.utils import deep_update

logger = logging.getLogger()


class R2RConfig:
    current_file_path = os.path.dirname(__file__)
    config_dir_root = os.path.join(current_file_path, "..", "configs")
    default_config_path = os.path.join(
        current_file_path, "..", "..", "r2r", "r2r.toml"
    )

    CONFIG_OPTIONS: dict[str, Optional[str]] = {}
    for file_ in os.listdir(config_dir_root):
        if file_.endswith(".toml"):
            CONFIG_OPTIONS[file_.removesuffix(".toml")] = os.path.join(
                config_dir_root, file_
            )
    CONFIG_OPTIONS["default"] = None

    REQUIRED_KEYS: dict[str, list] = {
        "app": [],
        "completion": ["provider"],
        "crypto": ["provider"],
        "email": ["provider"],
        "auth": ["provider"],
        "embedding": [
            "provider",
            "base_model",
            "base_dimension",
            "batch_size",
            "add_title_as_prefix",
        ],
        "completion_embedding": [
            "provider",
            "base_model",
            "base_dimension",
            "batch_size",
            "add_title_as_prefix",
        ],
        # TODO - deprecated, remove
        "ingestion": ["provider"],
        "logging": ["provider", "log_table"],
        "database": ["provider"],
        "agent": ["generation_config"],
        "orchestration": ["provider"],
    }

    app: AppConfig
    auth: AuthConfig
    completion: CompletionConfig
    crypto: CryptoConfig
    database: DatabaseConfig
    embedding: EmbeddingConfig
    completion_embedding: EmbeddingConfig
    email: EmailConfig
    ingestion: IngestionConfig
    agent: RAGAgentConfig
    orchestration: OrchestrationConfig

    def __init__(self, config_data: dict[str, Any]):
        """
        :param config_data: dictionary of configuration parameters
        :param base_path: base path when a relative path is specified for the prompts directory
        """
        # Load the default configuration
        default_config = self.load_default_config()

        # Override the default configuration with the passed configuration
        default_config = deep_update(default_config, config_data)

        # Validate and set the configuration
        for section, keys in R2RConfig.REQUIRED_KEYS.items():
            # Check the keys when provider is set
            # TODO - remove after deprecation
            if section in ["graph", "file"] and section not in default_config:
                continue
            if "provider" in default_config[section] and (
                default_config[section]["provider"] is not None
                and default_config[section]["provider"] != "None"
                and default_config[section]["provider"] != "null"
            ):
                self._validate_config_section(default_config, section, keys)
            setattr(self, section, default_config[section])

        self.app = AppConfig.create(**self.app)  # type: ignore
        self.auth = AuthConfig.create(**self.auth, app=self.app)  # type: ignore
        self.completion = CompletionConfig.create(
            **self.completion, app=self.app
        )  # type: ignore
        self.crypto = CryptoConfig.create(**self.crypto, app=self.app)  # type: ignore
        self.email = EmailConfig.create(**self.email, app=self.app)  # type: ignore
        self.database = DatabaseConfig.create(**self.database, app=self.app)  # type: ignore
        self.embedding = EmbeddingConfig.create(**self.embedding, app=self.app)  # type: ignore
        self.completion_embedding = EmbeddingConfig.create(
            **self.completion_embedding, app=self.app
        )  # type: ignore
        self.ingestion = IngestionConfig.create(**self.ingestion, app=self.app)  # type: ignore
        self.agent = RAGAgentConfig.create(**self.agent, app=self.app)  # type: ignore
        self.orchestration = OrchestrationConfig.create(
            **self.orchestration, app=self.app
        )  # type: ignore

        IngestionConfig.set_default(**self.ingestion.dict())

        # override GenerationConfig defaults
        if self.completion.generation_config:
            GenerationConfig.set_default(
                **self.completion.generation_config.dict()
            )

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
    def from_toml(cls, config_path: Optional[str] = None) -> "R2RConfig":
        if config_path is None:
            config_path = R2RConfig.default_config_path

        # Load configuration from TOML file
        with open(config_path, encoding="utf-8") as f:
            config_data = toml.load(f)

        return cls(config_data)

    def to_toml(self):
        config_data = {}
        for section in R2RConfig.REQUIRED_KEYS.keys():
            section_data = self._serialize_config(getattr(self, section))
            if isinstance(section_data, dict):
                # Remove app from nested configs before serializing
                section_data.pop("app", None)
            config_data[section] = section_data
        return toml.dumps(config_data)

    @classmethod
    def load_default_config(cls) -> dict:
        with open(R2RConfig.default_config_path, encoding="utf-8") as f:
            return toml.load(f)

    @staticmethod
    def _serialize_config(config_section: Any):
        """Serialize config section while excluding internal state."""
        if isinstance(config_section, dict):
            return {
                R2RConfig._serialize_key(k): R2RConfig._serialize_config(v)
                for k, v in config_section.items()
                if k != "app"  # Exclude app from serialization
            }
        elif isinstance(config_section, (list, tuple)):
            return [
                R2RConfig._serialize_config(item) for item in config_section
            ]
        elif isinstance(config_section, Enum):
            return config_section.value
        elif isinstance(config_section, BaseModel):
            data = config_section.model_dump(exclude_none=True)
            data.pop("app", None)  # Remove app from the serialized data
            return R2RConfig._serialize_config(data)
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
            raise ValueError(
                f"Cannot specify both config_path and config_name. Got: {config_path}, {config_name}"
            )

        if config_path := os.getenv("R2R_CONFIG_PATH") or config_path:
            return cls.from_toml(config_path)

        config_name = os.getenv("R2R_CONFIG_NAME") or config_name or "default"
        if config_name not in R2RConfig.CONFIG_OPTIONS:
            raise ValueError(f"Invalid config name: {config_name}")
        return cls.from_toml(R2RConfig.CONFIG_OPTIONS[config_name])
