import logging
import uuid
from abc import abstractmethod
from typing import Any, AsyncGenerator, Optional, Union

from r2r.base import (
    AsyncPipe,
    AsyncState,
    KVLoggingSingleton,
    PipeType,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)


class SearchPipe(AsyncPipe):
    class SearchConfig(AsyncPipe.PipeConfig):
        name: str = "default_vector_search"
        search_filters: dict = {}
        search_limit: int = 10

    class Input(AsyncPipe.Input):
        message: Union[AsyncGenerator[str, None], str]

    def __init__(
        self,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        type: PipeType = PipeType.SEARCH,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config,
            *args,
            **kwargs,
        )

    @abstractmethod
    async def search(
        self,
        query: str,
        filters: dict[str, Any] = {},
        limit: int = 10,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        pass

    @abstractmethod
    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: uuid.UUID,
        *args: Any,
        **kwargs,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        pass
