"""
Abstract base class for embedding pipe.
"""

import logging
from abc import abstractmethod
from typing import AsyncGenerator, Optional, Union

from r2r.core import (
    AsyncContext,
    LoggingDatabaseConnectionSingleton,
    PipeConfig,
    PipeType,
    SearchRequest,
    SearchResult,
    VectorDBProvider,
)

from ..abstractions.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class SearchPipe(LoggableAsyncPipe):
    def __init__(
        self,
        config: PipeConfig,
        vector_db_provider: VectorDBProvider,
        logging_connection: Optional[
            LoggingDatabaseConnectionSingleton
        ] = None,
        *args,
        **kwargs,
    ):
        self.vector_db_provider = vector_db_provider
        super().__init__(
            config=config,
            logging_connection=logging_connection,
            *args,
            **kwargs,
        )

    @property
    def type(self) -> PipeType:
        return PipeType.SEARCH

    @abstractmethod
    async def search(self, input: str) -> AsyncGenerator[SearchResult, None]:
        pass

    @abstractmethod
    async def _run_logic(
        self,
        input: Union[AsyncGenerator[str, None], str],
        context: AsyncContext,
        **kwargs,
    ) -> AsyncGenerator[SearchResult, None]:
        pass
