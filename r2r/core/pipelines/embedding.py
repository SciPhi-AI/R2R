"""
Abstract base class for embedding pipelines.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..providers.embedding import EmbeddingProvider
from ..providers.logging import LoggingDatabaseConnection
from ..providers.vector_db import VectorDBProvider, VectorEntry


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
    def transform_chunks(
        self, chunks: list[Any], metadatas: list[dict]
    ) -> list[Any]:
        pass

    @abstractmethod
    def embed_chunks(self, chunks: list[Any]) -> list[list[float]]:
        pass

    @abstractmethod
    def process_batches(self, batch: list[Any]) -> None:
        pass

    @abstractmethod
    def store_chunks(self, chunks: list[VectorEntry]) -> None:
        pass

    @abstractmethod
    def run(self, document: Any, **kwargs):
        pass
