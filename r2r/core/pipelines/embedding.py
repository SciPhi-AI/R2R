"""
Abstract base class for embedding pipelines.
"""

import logging
from abc import abstractmethod
from typing import AsyncGenerator, Generator, Optional

from ..abstractions.document import Extraction, Fragment
from ..providers.embedding import EmbeddingProvider
from ..providers.vector_db import VectorDBProvider, VectorEntry
from ..utils import generate_run_id
from ..utils.logging import LoggingDatabaseConnection
from .async_pipeline import AsyncPipeline

logger = logging.getLogger(__name__)


class EmbeddingPipeline(AsyncPipeline):
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.embedding_provider = embedding_provider
        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipeline(self, *args, **kwargs) -> None:
        self.pipeline_run_info = {
            "run_id": generate_run_id(),
            "type": "embedding",
        }

    @abstractmethod
    async def fragment(
        self, extraction: Extraction
    ) -> AsyncGenerator[Fragment, None]:
        pass

    @abstractmethod
    async def transform_fragments(
        self, fragments: list[Fragment], metadatas: list[dict]
    ) -> AsyncGenerator[Fragment, None]:
        pass

    @abstractmethod
    async def embed(self, fragments: list[Fragment]) -> list[list[float]]:
        pass

    @abstractmethod
    async def run(
        self, extractions: AsyncGenerator[Extraction, None], **kwargs
    ) -> VectorEntry:
        pass
