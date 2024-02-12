"""
Abstract base class for embedding pipelines.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..providers.dataset import DatasetProvider
from ..providers.embedding import EmbeddingProvider
from ..providers.vector_db import VectorDBProvider, VectorEntry
from .logging import LoggingDatabaseConnection


# TODO - Create a new class `Pipeline`
# and move the common methods between `RAGPipeline`
# and `EmbeddingPipeline` to it.
class EmbeddingPipeline(ABC):
    def __init__(
        self,
        embedding_model: str,
        embeddings_provider: EmbeddingProvider,
        db: VectorDBProvider,
        logging_database: Optional[LoggingDatabaseConnection] = None,
        **kwargs
    ):
        self.embedding_model = embedding_model
        self.embeddings_provider = embeddings_provider
        self.db = db
        self.logging_database = logging_database

        if logging_database is not None:
            self.conn = logging_database.__enter__()
            self.log_table_name = logging_database.log_table_name
        else:
            self.conn = None
            self.log_table_name = None

    def close(self):
        if self.logging_database:
            self.logging_database.__exit__(None, None, None)

    @abstractmethod
    def extract_text(self, document: Any) -> str:
        pass

    @abstractmethod
    def transform_text(self, text: str) -> str:
        pass

    @abstractmethod
    def chunk_text(self, text: str) -> list[str]:
        pass

    @abstractmethod
    def transform_chunk(self, chunk: Any) -> Any:
        pass

    @abstractmethod
    def embed_chunk(self, chunk: Any) -> list[float]:
        pass

    @abstractmethod
    def store_chunks(self, chunks: list[VectorEntry]) -> None:
        pass

    @abstractmethod
    def run(self, document: Any):
        pass