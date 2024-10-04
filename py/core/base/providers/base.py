from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from pydantic import BaseModel

from ..abstractions import R2RSerializable


class AppConfig(R2RSerializable):
    project_name: Optional[str] = None

    @classmethod
    def create(cls, *args, **kwargs):
        project_name = kwargs.get("project_name")
        return AppConfig(project_name=project_name)


class ProviderConfig(BaseModel, ABC):
    """A base provider configuration class"""

    app: AppConfig  # Add an app_config field
    extra_fields: dict[str, Any] = {}
    provider: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        ignore_extra = True

    @abstractmethod
    def validate_config(self) -> None:
        pass

    @classmethod
    def create(cls: Type["ProviderConfig"], **kwargs: Any) -> "ProviderConfig":
        base_args = cls.model_fields.keys()
        filtered_kwargs = {
            k: v if v != "None" else None
            for k, v in kwargs.items()
            if k in base_args
        }
        instance = cls(**filtered_kwargs)
        for k, v in kwargs.items():
            if k not in base_args:
                instance.extra_fields[k] = v
        return instance

    @property
    @abstractmethod
    def supported_providers(self) -> list[str]:
        """Define a list of supported providers."""
        pass

    @classmethod
    def from_dict(
        cls: Type["ProviderConfig"], data: dict[str, Any]
    ) -> "ProviderConfig":
        """Create a new instance of the config from a dictionary."""
        return cls.create(**data)


class Provider(ABC):
    """A base provider class to provide a common interface for all providers."""

    def __init__(self, config: ProviderConfig, *args, **kwargs):
        if config:
            config.validate_config()
        self.config = config
