import logging
from abc import abstractmethod
from typing import Any, AsyncGenerator, Optional, Union

from r2r.core import (
    AsyncPipe,
    AsyncState,
    LoggingDatabaseConnectionSingleton,
    PipeFlow,
    PipeType,
    SearchResult,
    VectorDBProvider,
)

from ..abstractions.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class SearchPipe(LoggableAsyncPipe):
    class SearchConfig(AsyncPipe.PipeConfig):
        name: str = "default_vector_search"
        filters: dict = {}
        limit: int = 10

    class Input(AsyncPipe.Input):
        message: Union[AsyncGenerator[str, None], str]

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        logging_connection: Optional[
            LoggingDatabaseConnectionSingleton
        ] = None,
        flow: PipeFlow = PipeFlow.STANDARD,
        type: PipeType = PipeType.SEARCH,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            logging_connection=logging_connection,
            flow=flow,
            type=type,
            config=config,
            *args,
            **kwargs,
        )
        self.vector_db_provider = vector_db_provider

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
        state: AsyncState,
        **kwargs,
    ) -> AsyncGenerator[SearchResult, None]:
        pass
