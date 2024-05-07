"""
Abstract base class for embedding pipe.
"""

import logging
from abc import abstractmethod
from typing import AsyncGenerator, Generator, Optional

from ..abstractions.document import Extraction, Fragment
from ..abstractions.pipes import AsyncPipe, PipeType
from ..providers.embedding import EmbeddingProvider
from ..providers.vector_db import VectorDBProvider, VectorEntry
from ..utils import generate_run_id
from ..utils.logging import LoggingDatabaseConnection
from .loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class StoragePipe(LoggableAsyncPipe):
    INPUT_TYPE = AsyncGenerator[VectorEntry, None]
    OUTPUT_TYPE = None

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.vector_db_provider = vector_db_provider
        super().__init__(logging_connection=logging_connection, **kwargs)

    @property
    def type(self) -> PipeType:
        return PipeType.STORAGE

    @abstractmethod
    async def store(self, vector_entries: list[VectorEntry]) -> None:
        pass
