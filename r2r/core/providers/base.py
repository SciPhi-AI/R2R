from abc import ABC, abstractmethod, abstractproperty
from dataclasses import fields
from typing import List, Optional


class ProviderConfig(ABC):
    """A base provider configuration class"""

    @abstractmethod
    def validate(self) -> None:
        pass

    @classmethod
    def create(cls, **kwargs):
        valid_keys = {f.name for f in fields(cls)}
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_keys}
        instance = cls(**filtered_kwargs)
        instance.extras = {
            k: v for k, v in kwargs.items() if k not in valid_keys
        }
        return instance

    @abstractproperty
    def supported_providers(self) -> List[str]:
        """Define a list of supported providers."""
        pass


class Provider(ABC):
    """A base provider class to provide a common interface for all providers."""

    def __init__(self, config: Optional[ProviderConfig] = None):
        if config:
            config.validate()
        self.config = config
