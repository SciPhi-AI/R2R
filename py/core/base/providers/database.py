import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class DatabaseConfig(ProviderConfig):
    """A base database configuration class"""

    provider: str = "postgres"
    user: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    db_name: Optional[str] = None
    vecs_collection: Optional[str] = None
    project_name: Optional[str] = None

    def __post_init__(self):
        self.validate_config()
        # Capture additional fields
        for key, value in self.extra_fields.items():
            setattr(self, key, value)

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["postgres"]


class VectorDBProvider(Provider, ABC):
    @abstractmethod
    def _initialize_vector_db(self, dimension: int) -> None:
        pass


class RelationalDBProvider(Provider, ABC):
    @abstractmethod
    async def _initialize_relational_db(self) -> None:
        pass


class DatabaseProvider(Provider):
    def __init__(self, config: DatabaseConfig):
        if not isinstance(config, DatabaseConfig):
            raise ValueError(
                "DatabaseProvider must be initialized with a `DatabaseConfig`."
            )
        logger.info(f"Initializing DatabaseProvider with config {config}.")
        super().__init__(config)

        # remove later to re-introduce typing...
        self.vector: Any = None
        self.relational: Any = None

    @abstractmethod
    def _initialize_vector_db(self) -> VectorDBProvider:
        pass

    @abstractmethod
    async def _initialize_relational_db(self) -> RelationalDBProvider:
        pass
