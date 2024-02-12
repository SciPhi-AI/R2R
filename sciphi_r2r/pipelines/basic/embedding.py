"""
A simple example to demonstrate the usage of `BasicEmbeddingPipeline`.
"""
import logging
import uuid
from typing import Any

from langchain.text_splitter import TextSplitter

from sciphi_r2r.core import (EmbeddingPipeline, LoggingDatabaseConnection,
                             VectorEntry, log_execution_to_db)
from sciphi_r2r.datasets import HuggingFaceDataProvider
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider
from sciphi_r2r.vector_dbs import PGVectorDB

logger = logging.getLogger("sciphi_r2r")


class BasicEmbeddingPipeline(EmbeddingPipeline):
    def __init__(
        self,
        dataset_provider: HuggingFaceDataProvider,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
        db: PGVectorDB,
        logging_database: LoggingDatabaseConnection,
        text_splitter: TextSplitter,
    ):
        logger.debug(f"Initalizing `BasicEmbeddingPipeline`.")

        super().__init__(
            dataset_provider,
            embedding_model,
            embeddings_provider,
            db,
            logging_database,
        )
        self.text_splitter = text_splitter

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

    def _stream_texts(self):
        return self.dataset_provider.stream_text()

    def run(self):
        logger.debug(f"Running the `DemoEmbeddingPipeline`.")
        self.pipeline_run_id = uuid.uuid4()

        entries = []
        j = 0
        for text, config, i in self._stream_texts():
            logging.debug(f"Streaming {text}")
            chunks = self.chunk_text(text)
            for chunk in chunks:
                transformed_chunk = self.transform_chunk(chunk)
                embedded_chunk = self.embed_chunk(transformed_chunk)
                entries.append(
                    VectorEntry(
                        f"{config.name}_vec_{j}",
                        embedded_chunk,
                        {"text": chunk},
                    )
                )
                j += 1
            if i >= config.max_entries:
                j = 0
                break

        self.store_chunks(entries)
        logger.debug("Finished processing all documents")
