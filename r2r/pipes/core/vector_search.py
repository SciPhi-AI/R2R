"""
A simple example to demonstrate the usage of `DefaultEmbeddingPipe`.
"""

import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import (
    EmbeddingProvider,
    LoggingDatabaseConnection,
    SearchPipe,
    SearchRequest,
    SearchResult,
    VectorDBProvider,
)

logger = logging.getLogger(__name__)


class DefaultVectorSearchPipe(SearchPipe):
    """
    Stores embeddings in a vector database asynchronously.
    """

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        embedding_provider: EmbeddingProvider,
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
            vector_db_provider=vector_db_provider,
            logging_connection=logging_connection,
            *args,
            **kwargs,
        )
        self.embedding_provider = embedding_provider

    async def search(
        self,
        request: SearchRequest,
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
        input: SearchRequest,
        **kwargs: Any,
    ) -> AsyncGenerator[SearchResult, None]:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        self._initialize_pipe()
        async for result in self.search(request=input):
            yield result
