import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class PostgresConfigurationSettings(BaseModel):
    """
    Configuration settings with defaults defined by the PGVector docker image.

    These settings are helpful in managing the connections to the database.
    To tune these settings for a specific deployment, see https://pgtune.leopard.in.ua/
    """

    max_connections: Optional[int] = 100
    shared_buffers: Optional[int] = 16384
    effective_cache_size: Optional[int] = 524288
    maintenance_work_mem: Optional[int] = 65536
    checkpoint_completion_target: Optional[float] = 0.9
    wal_buffers: Optional[int] = 512
    default_statistics_target: Optional[int] = 100
    random_page_cost: Optional[float] = 4
    effective_io_concurrency: Optional[int] = 1
    work_mem: Optional[int] = 4096
    huge_pages: Optional[str] = "try"
    min_wal_size: Optional[int] = 80
    max_wal_size: Optional[int] = 1024
    max_worker_processes: Optional[int] = 8
    max_parallel_workers_per_gather: Optional[int] = 2
    max_parallel_workers: Optional[int] = 8
    max_parallel_maintenance_workers: Optional[int] = 2


class DatabaseConfig(ProviderConfig):
    """A base database configuration class"""

    provider: str = "postgres"
    user: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    db_name: Optional[str] = None
    project_name: Optional[str] = None
    postgres_configuration_settings: Optional[
        PostgresConfigurationSettings
    ] = None
    default_collection_name: str = "Default"
    default_collection_description: str = "Your default collection."

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

    @abstractmethod
    def _get_table_name(self, base_name: str) -> str:
        pass
