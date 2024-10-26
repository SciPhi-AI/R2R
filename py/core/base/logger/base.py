import logging
from abc import abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Tuple, Union
from uuid import UUID

from pydantic import BaseModel

from core.base import Message

from ..providers.base import Provider, ProviderConfig

logger = logging.getLogger()


class RunInfoLog(BaseModel):
    run_id: UUID
    run_type: str
    timestamp: datetime
    user_id: UUID


class PersistentLoggingConfig(ProviderConfig):
    provider: str = "local"
    log_table: str = "logs"
    log_info_table: str = "log_info"
    logging_path: Optional[str] = None

    def validate_config(self) -> None:
        pass

    @property
    def supported_providers(self) -> list[str]:
        return ["local", "postgres"]


class RunType(str, Enum):
    """Enumeration of the different types of runs."""

    RETRIEVAL = "RETRIEVAL"
    MANAGEMENT = "MANAGEMENT"
    INGESTION = "INGESTION"
    AUTH = "AUTH"
    UNSPECIFIED = "UNSPECIFIED"
    KG = "KG"


class PersistentLoggingProvider(Provider):
    @abstractmethod
    async def close(self):
        pass

    @abstractmethod
    async def log(
        self,
        run_id: UUID,
        key: str,
        value: str,
    ):
        pass

    @abstractmethod
    async def get_logs(
        self,
        run_ids: list[UUID],
        limit_per_run: int,
    ) -> list:
        pass

    @abstractmethod
    async def info_log(
        self,
        run_id: UUID,
        run_type: RunType,
        user_id: UUID,
    ):
        pass

    @abstractmethod
    async def get_info_logs(
        self,
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        pass
