"""
A simple example to demonstrate the usage of `BasicEmbeddingPipeline`.
"""
import logging
import uuid
from typing import Any, Optional, Union

from langchain.text_splitter import TextSplitter
from pydantic import BaseModel

from sciphi_r2r.core import (
    EmbeddingPipeline,
    LoggingDatabaseConnection,
    VectorEntry,
    log_execution_to_db,
)
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider
from sciphi_r2r.vector_dbs import PGVectorDB

logger = logging.getLogger("sciphi_r2r")


class BasicDocument(BaseModel):
    id: str
    text: str
    metadata: Optional[dict]


class BasicEmbeddingPipeline(EmbeddingPipeline):
    def __init__(
        self,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
        db: PGVectorDB,
        logging_database: LoggingDatabaseConnection,
        text_splitter: TextSplitter,
        id_prefix: str = "demo",
    ):
        logger.debug(f"Initalizing `BasicEmbeddingPipeline`.")

        super().__init__(
            embedding_model,
            embeddings_provider,
            db,
            logging_database,
        )
        self.text_splitter = text_splitter
        self.id_prefix = id_prefix

    def extract_text(self, document: Any) -> str:
        return next(document)[0]

    def transform_text(self, text: str) -> str:
        return text

    @log_execution_to_db
    def chunk_text(self, text: str) -> list[str]:
        return [
            ele.page_content
            for ele in self.text_splitter.create_documents([text])
        ]

    def transform_chunk(self, chunk: Any) -> Any:
        return chunk

    def embed_chunk(self, chunk: Any) -> list[float]:
        return self.embeddings_provider.get_embedding(
            chunk, self.embedding_model
        )

    def store_chunks(self, chunks: list[VectorEntry]) -> None:
        self.db.upsert_entries(chunks)

    def run(
        self,
        document: Union[BasicDocument, list[BasicDocument]],
        **kwargs: Any,
    ):
        self.pipeline_run_id = uuid.uuid4()
        logger.debug(
            f"Running the `DemoEmbeddingPipeline` with id={self.pipeline_run_id}."
        )

        entries = []
        documents = [document] if not isinstance(document, list) else document

        for document in documents:
            chunks = self.chunk_text(document.text)
            metadata = document.metadata if document.metadata else {}
            metadata["pipeline_run_id"] = str(self.pipeline_run_id)

            for i, chunk in enumerate(chunks):
                transformed_chunk = self.transform_chunk(chunk)
                embedded_chunk = self.embed_chunk(transformed_chunk)
                metadata["text"] = chunk
                entries.append(
                    VectorEntry(
                        document.id + f"_chunk_{i}",
                        embedded_chunk,
                        metadata,
                    )
                )

        self.store_chunks(entries)
        logger.debug("Finished processing all documents")
