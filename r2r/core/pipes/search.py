"""
Abstract base class for embedding pipe.
"""

import logging
from abc import abstractmethod
from typing import AsyncGenerator, Optional

from ..abstractions.pipes import PipeType
from ..abstractions.search import SearchRequest, SearchResult
from ..providers.vector_db import VectorDBProvider
from ..utils.logging import LoggingDatabaseConnection
from .loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class SearchPipe(LoggableAsyncPipe):
    INPUT_TYPE = SearchRequest
    OUTPUT_TYPE = AsyncGenerator[SearchResult, None]

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.vector_db_provider = vector_db_provider
        super().__init__(
            logging_connection=logging_connection, *args, **kwargs
        )

    @property
    def pipe_type(self) -> PipeType:
        return PipeType.SEARCH

    @abstractmethod
    async def search(
        self, request: SearchRequest
    ) -> AsyncGenerator[SearchResult, None]:
        pass

    @abstractmethod
    async def run(self, input: INPUT_TYPE, **kwargs) -> OUTPUT_TYPE:
        pass
