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


class RunType(str, Enum):
    """Enumeration of the different types of runs."""

    RETRIEVAL = "RETRIEVAL"
    MANAGEMENT = "MANAGEMENT"
    INGESTION = "INGESTION"
    AUTH = "AUTH"
    UNSPECIFIED = "UNSPECIFIED"
    KG = "KG"
