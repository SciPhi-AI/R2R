import logging
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

from r2r.core import (
    AsyncContext,
    AsyncPipe,
    PipeConfig,
    PipeFlow,
    SearchResult,
)

from ..abstractions.aggregator import AggregatorPipe

logger = logging.getLogger(__name__)


class DefaultSearchRAGContextPipe(AggregatorPipe):
    """
    Stores embeddings in a vector database asynchronously.
    """

    class SearchRAGContextConfig(BaseModel, PipeConfig):
        name: str = "default_search_rag_context"

    class Input(AsyncPipe.Input):
        message: AsyncGenerator[SearchResult, None]

    def __init__(
        self,
        config: Optional[SearchRAGContextConfig] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the async vector storage pipe with necessary components and configurations.
        """
        logger.info(f"Initalizing an `DefaultVectorSearchPipe` pipe.")
        config = config or DefaultSearchRAGContextPipe.SearchRAGContextConfig()
        if not isinstance(
            config, DefaultSearchRAGContextPipe.SearchRAGContextConfig
        ):
            raise ValueError(
                "Invalid configuration provided for `DefaultSearchRAGContextPipe`."
            )

        super().__init__(
            config=config,
            *args,
            **kwargs,
        )

    @property
    def flow(self) -> PipeFlow:
        return PipeFlow.FAN_IN

    def input_from_dict(self, input_dict: dict) -> Input:
        return DefaultSearchRAGContextPipe.Input(**input_dict)

    async def _run_logic(
        self,
        input: Input,
        context: AsyncContext,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        await self.aggregate(input, context)
        if len(self.results) > 0:
            rag_context = "\n\n".join([str(ele) for ele in self.results])

        else:
            rag_context = "No results found."

        await context.update(
            self.config.name, {"output": {"rag_context": rag_context}}
        )
        print("yielding rag_context = ", rag_context)
        yield rag_context
