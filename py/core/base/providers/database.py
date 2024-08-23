import logging
from abc import ABC, abstractmethod

from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class DatabaseConfig(ProviderConfig):
    def __post_init__(self):
        self.validate()
        # Capture additional fields
        for key, value in self.extra_fields.items():
            setattr(self, key, value)

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["postgres", None]


class VectorDBProvider(Provider, ABC):
    @abstractmethod
    def _initialize_vector_db(self, dimension: int) -> None:
        pass


class RelationalDBProvider(Provider, ABC):
    @abstractmethod
    def _initialize_relational_db(self) -> None:
        pass


class DatabaseProvider(Provider):

    def __init__(self, config: DatabaseConfig):
        if not isinstance(config, DatabaseConfig):
            raise ValueError(
                "DatabaseProvider must be initialized with a `DatabaseConfig`."
            )
        logger.info(f"Initializing DatabaseProvider with config {config}.")
        super().__init__(config)
        self.vector: VectorDBProvider = self._initialize_vector_db()
        self.relational: RelationalDBProvider = (
            self._initialize_relational_db()
        )

    @abstractmethod
    def _initialize_vector_db(self) -> VectorDBProvider:
        pass

    @abstractmethod
    def _initialize_relational_db(self) -> RelationalDBProvider:
        pass
