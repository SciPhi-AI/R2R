"""
Abstract base class for embedding pipe.
"""

import logging
from abc import abstractmethod
from typing import AsyncGenerator, Generator, Optional

from r2r.core import (
    AsyncPipe,
    EmbeddingProvider,
    Extraction,
    Fragment,
    LoggingDatabaseConnection,
    PipeType,
    SearchRequest,
    SearchResult,
    VectorDBProvider,
    VectorEntry,
    generate_run_id,
)

from ..abstractions.loggable import LoggableAsyncPipe
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
