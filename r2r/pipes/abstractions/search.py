"""
Abstract base class for embedding pipe.
"""

import logging
from abc import abstractmethod
from typing import Any, AsyncGenerator, Optional, Union

from r2r.core import (
    AsyncContext,
    AsyncPipe,
    LoggingDatabaseConnectionSingleton,
    PipeConfig,
    PipeFlow,
    PipeType,
    SearchRequest,
    SearchResult,
    VectorDBProvider,
)

from ..abstractions.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class SearchPipe(LoggableAsyncPipe):
    class Input(AsyncPipe.Input):
        message: Union[AsyncGenerator[str, None], str]

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        logging_connection: Optional[
            LoggingDatabaseConnectionSingleton
        ] = None,
        config: Optional[PipeConfig] = None,
        flow: PipeFlow = PipeFlow.STANDARD,
        *args,
        **kwargs,
    ):
        self.vector_db_provider = vector_db_provider
        super().__init__(
            logging_connection=logging_connection,
            config=config,
            flow=flow,
            *args,
            **kwargs,
        )

    @property
    def type(self) -> PipeType:
        return PipeType.SEARCH

    @abstractmethod
    async def search(
        self,
        query: str,
        filters: dict[str, Any] = {},
        limit: int = 10,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[SearchResult, None]:
        pass

    @abstractmethod
    async def _run_logic(
        self,
        input: Input,
        context: AsyncContext,
        **kwargs,
    ) -> AsyncGenerator[SearchResult, None]:
        pass
