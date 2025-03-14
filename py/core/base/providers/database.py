"""Base classes for database providers."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Sequence, cast
from uuid import UUID

from pydantic import BaseModel

from core.base.abstractions import (
    GraphCreationSettings,
    GraphEnrichmentSettings,
    GraphSearchSettings,
)

from .base import Provider, ProviderConfig

logger = logging.getLogger()


class DatabaseConnectionManager(ABC):
    @abstractmethod
    def execute_query(
        self,
        query: str,
        params: Optional[dict[str, Any] | Sequence[Any]] = None,
        isolation_level: Optional[str] = None,
    ):
        pass

    @abstractmethod
    async def execute_many(self, query, params=None, batch_size=1000):
        pass

    @abstractmethod
    def fetch_query(
        self,
        query: str,
        params: Optional[dict[str, Any] | Sequence[Any]] = None,
    ):
        pass

    @abstractmethod
    def fetchrow_query(
        self,
        query: str,
        params: Optional[dict[str, Any] | Sequence[Any]] = None,
    ):
        pass

    @abstractmethod
    async def initialize(self, pool: Any):
        pass


class Handler(ABC):
    def __init__(
        self,
        project_name: str,
        connection_manager: DatabaseConnectionManager,
    ):
        self.project_name = project_name
        self.connection_manager = connection_manager

    def _get_table_name(self, base_name: str) -> str:
        return f"{self.project_name}.{base_name}"

    @abstractmethod
    def create_tables(self):
        pass


class PostgresConfigurationSettings(BaseModel):
    """Configuration settings with defaults defined by the PGVector docker
    image.

    These settings are helpful in managing the connections to the database. To
    tune these settings for a specific deployment, see
    https://pgtune.leopard.in.ua/
    """

    checkpoint_completion_target: Optional[float] = 0.9
    default_statistics_target: Optional[int] = 100
    effective_io_concurrency: Optional[int] = 1
    effective_cache_size: Optional[int] = 524288
    huge_pages: Optional[str] = "try"
    maintenance_work_mem: Optional[int] = 65536
    max_connections: Optional[int] = 256
    max_parallel_workers_per_gather: Optional[int] = 2
    max_parallel_workers: Optional[int] = 8
    max_parallel_maintenance_workers: Optional[int] = 2
    max_wal_size: Optional[int] = 1024
    max_worker_processes: Optional[int] = 8
    min_wal_size: Optional[int] = 80
    shared_buffers: Optional[int] = 16384
    statement_cache_size: Optional[int] = 100
    random_page_cost: Optional[float] = 4
    wal_buffers: Optional[int] = 512
    work_mem: Optional[int] = 4096


class LimitSettings(BaseModel):
    global_per_min: Optional[int] = None
    route_per_min: Optional[int] = None
    monthly_limit: Optional[int] = None

    def merge_with_defaults(
        self, defaults: "LimitSettings"
    ) -> "LimitSettings":
        return LimitSettings(
            global_per_min=self.global_per_min or defaults.global_per_min,
            route_per_min=self.route_per_min or defaults.route_per_min,
            monthly_limit=self.monthly_limit or defaults.monthly_limit,
        )


class DatabaseConfig(ProviderConfig):
    """A base database configuration class."""

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
    collection_summary_system_prompt: str = "system"
    collection_summary_prompt: str = "collection_summary"
    enable_fts: bool = False

    # Graph settings
    batch_size: Optional[int] = 1
    graph_search_results_store_path: Optional[str] = None
    graph_enrichment_settings: GraphEnrichmentSettings = (
        GraphEnrichmentSettings()
    )
    graph_creation_settings: GraphCreationSettings = GraphCreationSettings()
    graph_search_settings: GraphSearchSettings = GraphSearchSettings()

    # Rate limits
    limits: LimitSettings = LimitSettings(
        global_per_min=60, route_per_min=20, monthly_limit=10000
    )
    route_limits: dict[str, LimitSettings] = {}
    user_limits: dict[UUID, LimitSettings] = {}

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["postgres"]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DatabaseConfig":
        instance = cls.create(**data)

        instance = cast(DatabaseConfig, instance)

        limits_data = data.get("limits", {})
        default_limits = LimitSettings(
            global_per_min=limits_data.get("global_per_min", 60),
            route_per_min=limits_data.get("route_per_min", 20),
            monthly_limit=limits_data.get("monthly_limit", 10000),
        )

        instance.limits = default_limits

        route_limits_data = limits_data.get("routes", {})
        for route_str, route_cfg in route_limits_data.items():
            instance.route_limits[route_str] = LimitSettings(**route_cfg)

        return instance


class DatabaseProvider(Provider):
    connection_manager: DatabaseConnectionManager
    config: DatabaseConfig
    project_name: str

    def __init__(self, config: DatabaseConfig):
        logger.info(f"Initializing DatabaseProvider with config {config}.")
        super().__init__(config)

    @abstractmethod
    async def __aenter__(self):
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb):
        pass
