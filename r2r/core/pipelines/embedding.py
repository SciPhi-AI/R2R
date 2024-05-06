"""
Abstract base class for embedding pipelines.
"""

import logging
from abc import abstractmethod
from typing import Any, Generator, Optional

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
        vector_db_provider: VectorDBProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.embedding_provider = embedding_provider
        self.vector_db_provider = vector_db_provider
        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipeline(self, *args, **kwargs) -> None:
        self.pipeline_run_info = {
            "run_id": generate_run_id(),
            "type": "embedding",
        }

    @abstractmethod
    def fragment(self, extraction: Extraction) -> list[Fragment]:
        pass

    @abstractmethod
    async def transform_fragments(
        self, fragments: list[Fragment], metadatas: list[dict]
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def embed_fragments(
        self, fragments: list[Fragment]
    ) -> list[list[float]]:
        pass

    @abstractmethod
    async def run(
        self, extractions: Generator[Extraction, None, None], **kwargs
    ) -> VectorEntry:
        pass
