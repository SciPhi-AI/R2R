import logging
from abc import abstractmethod
from typing import Any, AsyncGenerator, Optional, Union
from uuid import UUID

from core.base import AsyncPipe, AsyncState, VectorSearchResult
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider

logger = logging.getLogger()


class SearchPipe(AsyncPipe[VectorSearchResult]):
    class SearchConfig(AsyncPipe.PipeConfig):
        name: str = "default_vector_search"
        filters: dict = {}
        search_limit: int = 10

    class Input(AsyncPipe.Input):
        message: Union[AsyncGenerator[str, None], str]

    def __init__(
        self,
        config: AsyncPipe.PipeConfig,
        logging_provider: SqlitePersistentLoggingProvider,
        *args,
        **kwargs,
    ):
        super().__init__(
            config,
            logging_provider,
            *args,
            **kwargs,
        )

    @abstractmethod
    async def search(
        self,
        query: str,
        search_settings: Any,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        pass

    @abstractmethod
    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        pass
