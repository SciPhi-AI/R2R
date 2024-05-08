import logging
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

from r2r.core import (
    Context,
    LoggingDatabaseConnection,
    PipeConfig,
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

    def __init__(
        self,
        config: Optional[SearchRAGContextConfig] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the async vector storage pipe with necessary components and configurations.
        """
        logger.info(f"Initalizing an `DefaultVectorSearchPipe` pipe.")
        if config and not isinstance(
            config, DefaultSearchRAGContextPipe.SearchRAGContextConfig
        ):
            raise ValueError(
                "Invalid configuration provided for `DefaultSearchRAGContextPipe`."
            )

        super().__init__(
            config=config
            or DefaultSearchRAGContextPipe.SearchRAGContextConfig(),
            logging_connection=logging_connection,
            *args,
            **kwargs,
        )

    async def run(
        self,
        input: AsyncGenerator[SearchResult, None],
        context: Context,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        await self._initialize_pipe(input, context)
        await self.aggregate(input, context)
        print("self.results = ", self.results)
        return "\n\n".join([str(ele) for ele in self.results])
