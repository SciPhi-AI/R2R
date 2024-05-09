import logging
from typing import Any, AsyncGenerator, Optional, Union

from pydantic import BaseModel

from r2r.core import (
    AsyncContext,
    AsyncPipe,
    EmbeddingProvider,
    PipeConfig,
    PipeFlow,
    PipeType,
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

    class Input(AsyncPipe.Input):
        message: Union[str, AsyncGenerator[str, None]]

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        embedding_provider: EmbeddingProvider,
        config: Optional[VectorSearchConfig] = None,
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
            *args,
            **kwargs,
        )
        self.embedding_provider = embedding_provider

    @property
    def flow(self) -> PipeFlow:
        return PipeFlow.FAN_OUT

    def input_from_dict(self, input_dict: dict) -> Input:
        print("input_dict = ", input_dict)
        return DefaultVectorSearchPipe.Input(**input_dict)

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

    async def _run_logic(
        self,
        input: Input,
        context: AsyncContext,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[SearchResult, None]:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        print("input = ", input)

        search_results = []

        if isinstance(input.message, AsyncGenerator):
            async for search_request in input.message:
                if isinstance(search_request, str):
                    async for result in self.search(message=search_request):
                        search_results.append(result)
                        yield result
        elif isinstance(input.message, str):
            async for result in self.search(message=input.message):
                search_results.append(result)
                yield result
        else:
            raise TypeError("Input must be an AsyncGenerator or a string.")

        await context.update(
            self.config.name, {"output": {"search_results": search_results}}
        )
