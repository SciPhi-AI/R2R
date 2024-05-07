"""
A simple example to demonstrate the usage of `DefaultEmbeddingPipe`.
"""

import logging
from typing import Any, AsyncGenerator, Optional, Type

from pydantic import BaseModel

from r2r.core import (
    EmbeddingProvider,
    LLMProvider,
    LoggingDatabaseConnection,
    PromptProvider,
    SearchRequest,
    SearchResult,
    VectorDBProvider,
)

from ..abstractions.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    query: str
    settings: dict
    
class DefaultQueryTransformPipe(LoggableAsyncPipe):
    """
    Stores embeddings in a vector database asynchronously.
    """
    INPUT_TYPE = QueryRequest
    OUTPUT_TYPE = list[str]

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the async vector storage pipe with necessary components and configurations.
        """
        logger.info(
            f"Initalizing an `AsyncVectorStoragePipe` to store embeddings in a vector database."
        )

        super().__init__(
            logging_connection=logging_connection,
            *args,
            **kwargs,
        )

    async def transform(
        self,
        request: QueryRequest,
    ) -> AsyncGenerator[SearchResult, None]:
        """
        Stores a batch of vector entries in the database.
        """
        for result in self.vector_db_provider.search(
            query_vector=self.embedding_provider.get_embedding(
                request.query,
            ),
            filters=request.filters,
            limit=request.limit,
        ):
            yield result

    async def run(
        self,
        input: QueryRequest,
        *args: Any,
        **kwargs: Any,
    ) -> OUTPUT_TYPE:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        self._initialize_pipe()
        async for result in self.transform(request=input):
            yield result
