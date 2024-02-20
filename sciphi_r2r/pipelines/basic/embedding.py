"""
A simple example to demonstrate the usage of `BasicEmbeddingPipeline`.
"""
import copy
import logging
import uuid
from typing import Any, Optional, Tuple, Union

from langchain.text_splitter import TextSplitter

from sciphi_r2r.core import (
    BasicDocument,
    EmbeddingPipeline,
    LoggingDatabaseConnection,
    VectorDBProvider,
    VectorEntry,
)
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider

logger = logging.getLogger(__name__)


class BasicEmbeddingPipeline(EmbeddingPipeline):
    def __init__(
        self,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
        db: VectorDBProvider,
        text_splitter: TextSplitter,
        logging_database: Optional[LoggingDatabaseConnection] = None,
        embedding_batch_size: int = 1,
        id_prefix: str = "demo",
    ):
        logger.info(
            f"Initalizing a `BasicEmbeddingPipeline` to embed and store documents."
        )

        super().__init__(
            embedding_model,
            embeddings_provider,
            db,
            logging_database,
        )
        self.text_splitter = text_splitter
        self.embedding_batch_size = embedding_batch_size
        self.id_prefix = id_prefix

    def extract_text(self, document: Any) -> str:
        return next(document)[0]

    def transform_text(self, text: str) -> str:
        return text

    def chunk_text(self, text: str) -> list[str]:
        return [
            ele.page_content
            for ele in self.text_splitter.create_documents([text])
        ]

    def transform_chunks(
        self, chunks: list[str], metadata: list[dict]
    ) -> list[str]:
        return chunks

    def embed_chunks(self, chunks: list[str]) -> list[list[float]]:
        return self.embeddings_provider.get_embeddings(
            chunks, self.embedding_model
        )

    def store_chunks(self, chunks: list[VectorEntry]) -> None:
        self.db.upsert_entries(chunks)

    def process_batches(self, batch_data: list[Tuple[str, str, dict]]):
        logger.debug(f"Parsing batch of size {len(batch_data)}.")

        entries = []

        # Unpack document IDs, indices, and chunks for transformation and embedding
        ids, raw_chunks, metadata = zip(*batch_data)
        transformed_chunks = self.transform_chunks(raw_chunks, metadata)
        embedded_chunks = self.embed_chunks(transformed_chunks)  # Batch embed

        for doc_id, original_chunk, embedded_chunk, metadatas in zip(
            ids, raw_chunks, embedded_chunks, metadata
        ):
            metadatas = copy.deepcopy(metadatas)
            metadatas["pipeline_run_id"] = str(self.pipeline_run_id)
            metadatas["text"] = original_chunk
            metadatas["document_id"] = doc_id
            chunk_id = uuid.uuid5(
                uuid.NAMESPACE_DNS, f"{doc_id}-{original_chunk}"
            )
            entries.append(VectorEntry(chunk_id, embedded_chunk, metadatas))
        self.store_chunks(entries)

    def run(
        self,
        document: Union[BasicDocument, list[BasicDocument]],
        do_chunking=False,
        **kwargs: Any,
    ):
        self.pipeline_run_id = uuid.uuid4()
        logger.debug(
            f"Running the `BasicEmbeddingPipeline` with id={self.pipeline_run_id}."
        )

        documents = [document] if not isinstance(document, list) else document
        batch_data = []

        for document in documents:
            chunks = (
                self.chunk_text(document.text)
                if do_chunking
                else [document.text]
            )
            for chunk in chunks:
                batch_data.append((document.id, chunk, document.metadata))

                if len(batch_data) == self.embedding_batch_size:
                    self.process_batches(batch_data)
                    batch_data = []

        # Process any remaining batch
        if batch_data:
            self.process_batches(batch_data)
