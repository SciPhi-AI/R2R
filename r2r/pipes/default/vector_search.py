import logging
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

from r2r.core import (
    Context,
    EmbeddingProvider,
    LoggingDatabaseConnection,
    PipeConfig,
    PipeFlow,
    PipeType,
    SearchRequest,
    SearchResult,
    VectorDBProvider,
)

from ..abstractions.search import SearchPipe

logger = logging.getLogger(__name__)


class DefaultVectorSearchPipe(SearchPipe):
    """
    Stores embeddings in a vector database asynchronously.
    """

    class VectorSearchConfig(BaseModel, PipeConfig):
        name: str = "default_vector_search"
        filters: dict = {}
        limit: int = 10
        system_prompt: str = "default_system_prompt"
        task_prompt: str = "hyde_prompt"

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        embedding_provider: EmbeddingProvider,
        config: Optional[VectorSearchConfig] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the async vector storage pipe with necessary components and configurations.
        """
        logger.info(f"Initalizing an `DefaultVectorSearchPipe` pipe.")
        if config and not isinstance(
            config, DefaultVectorSearchPipe.VectorSearchConfig
        ):
            raise ValueError(
                "Invalid configuration provided for `DefaultVectorSearchPipe`."
            )

        super().__init__(
            config=config or DefaultVectorSearchPipe.VectorSearchConfig(),
            vector_db_provider=vector_db_provider,
            logging_connection=logging_connection,
            *args,
            **kwargs,
        )
        self.embedding_provider = embedding_provider

    @property
    def type(self) -> PipeType:
        return PipeType.QUERY_TRANSFORM

    @property
    def flow(self) -> PipeFlow:
        return PipeFlow.FAN_OUT

    async def search(
        self,
        message: str,
    ) -> AsyncGenerator[SearchResult, None]:
        """
        Stores a batch of vector entries in the database.
        """
        for result in self.vector_db_provider.search(
            query_vector=self.embedding_provider.get_embedding(
                message,
            ),
            filters=self.config.filters,
            limit=self.config.limit,
        ):
            result.metadata["query"] = message
            yield result

    async def run(
        self,
        input: AsyncGenerator[str, None],
        context: Context,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[SearchResult, None]:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        print("input = ", input)
        await self._initialize_pipe(input, context)

        async for search_request in input:
            async for result in self.search(message=search_request):
                yield result
