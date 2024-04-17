"""
Abstract base class for embedding pipelines.
"""

import logging
from abc import abstractmethod
from typing import Any, Optional

from ..providers.embedding import EmbeddingProvider
from ..providers.logging import LoggingDatabaseConnection
from ..providers.vector_db import VectorDBProvider, VectorEntry
from ..utils import generate_run_id
from .pipeline import Pipeline

logger = logging.getLogger(__name__)


class EmbeddingPipeline(Pipeline):
    def __init__(
        self,
        embedding_model: str,
        embeddings_provider: EmbeddingProvider,
        db: VectorDBProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.embedding_model = embedding_model
        self.embeddings_provider = embeddings_provider
        self.db = db
        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipeline(self, *args, **kwargs) -> None:
        self.pipeline_run_info = {
            "run_id": generate_run_id(),
            "type": "embedding",
        }

    @abstractmethod
    def transform_text(self, text: str) -> str:
        pass

    @abstractmethod
    def chunk_text(self, text: str) -> list[str]:
        pass

    @abstractmethod
    def transform_chunks(
        self, chunks: list[Any], metadatas: list[dict]
    ) -> list[Any]:
        pass

    @abstractmethod
    def embed_chunks(self, chunks: list[Any]) -> list[list[float]]:
        pass

    @abstractmethod
    def store_chunks(self, chunks: list[VectorEntry], *args, **kwargs) -> None:
        pass

    def run(self, document: Any, **kwargs):
        pass
