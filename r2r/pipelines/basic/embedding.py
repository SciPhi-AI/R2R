"""
A simple example to demonstrate the usage of `BasicEmbeddingPipeline`.
"""

import copy
import logging
from typing import Any, Optional, Tuple

from r2r.core import (
    DocumentPage,
    EmbeddingPipeline,
    LoggingDatabaseConnection,
    VectorDBProvider,
    VectorEntry,
    log_execution_to_db,
)
from r2r.core.utils import TextSplitter, generate_id_from_label
from r2r.embeddings import OpenAIEmbeddingProvider

logger = logging.getLogger(__name__)


class BasicEmbeddingPipeline(EmbeddingPipeline):
    """
    Embeds and stores documents using a specified embedding model and database.
    """

    def __init__(
        self,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
        db: VectorDBProvider,
        text_splitter: TextSplitter,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        embedding_batch_size: int = 1,
        id_prefix: str = "demo",
    ):
        """
        Initializes the embedding pipeline with necessary components and configurations.
        """
        logger.info(
            f"Initalizing a `BasicEmbeddingPipeline` to embed and store documents."
        )

        super().__init__(
            embedding_model,
            embeddings_provider,
            db,
            logging_connection,
        )
        self.text_splitter = text_splitter
        self.embedding_batch_size = embedding_batch_size
        self.id_prefix = id_prefix
        self.pipeline_run_info = None

    @log_execution_to_db
    def ingress(self, document: DocumentPage) -> dict:
        """
        Extracts text from a document.
        """
        return {
            "document_id": str(document.document_id),
            "page_number": str(document.page_number),
            "metadata": document.metadata,
            "text": document.text,
        }

    def initialize_pipeline(
        self, document: DocumentPage, *args, **kwargs
    ) -> None:
        super().initialize_pipeline(*args, **kwargs)
        self.ingress(document)

    def transform_text(self, text: str) -> str:
        """
        Transforms text before chunking, if necessary.
        """
        return text

    def chunk_text(self, text: str) -> list[str]:
        """
        Splits text into manageable chunks for embedding.
        """
        return [
            ele.page_content
            for ele in self.text_splitter.create_documents([text])
        ]

    @log_execution_to_db
    def transform_chunks(
        self, chunks: list[str], metadatas: list[dict]
    ) -> list[str]:
        """
        Transforms text chunks based on their metadata, e.g., adding prefixes.
        """
        transformed_chunks = []
        for chunk, metadata in zip(chunks, metadatas):
            if "chunk_prefix" in metadata:
                prefix = metadata.pop("chunk_prefix")
                transformed_chunks.append(f"{prefix}\n{chunk}")
            else:
                transformed_chunks.append(chunk)
        return transformed_chunks

    def embed_chunks(self, chunks: list[str]) -> list[list[float]]:
        """
        Generates embeddings for each text chunk using the embedding model.
        """
        return self.embeddings_provider.get_embeddings(
            chunks, self.embedding_model
        )

    def store_chunks(
        self, chunks: list[VectorEntry], do_upsert: bool, *args, **kwargs
    ) -> None:
        """
        Stores the embedded chunks in the database, with an option to upsert.
        """
        if do_upsert:
            self.db.upsert_entries(chunks)
        else:
            self.db.copy_entries(chunks)

    def run(
        self,
        document: DocumentPage,
        do_chunking=False,
        do_upsert=True,
        **kwargs: Any,
    ):
        """
        Executes the embedding pipeline: chunking, transforming, embedding, and storing documents.
        """
        self.initialize_pipeline(document=document)

        logger.debug(
            f"Running the `BasicEmbeddingPipeline` with pipeline_run_info={self.pipeline_run_info}."
        )

        batch_data = []

        chunks = (
            self.chunk_text(document.text) if do_chunking else [document.text]
        )
        for chunk_iter, chunk in enumerate(chunks):
            batch_data.append(
                (
                    document.document_id,
                    document.page_number,
                    chunk_iter,
                    chunk,
                    copy.copy(document.metadata),
                )
            )

            if len(batch_data) == self.embedding_batch_size:
                self._process_batches(batch_data, do_upsert)
                batch_data = []

        # Process any remaining batch
        if batch_data:
            self._process_batches(batch_data, do_upsert)

    def _process_batches(
        self, batch_data: list[Tuple[str, str, dict]], do_upsert: bool
    ):
        """
        Processes batches of documents: transforms, embeds, and stores chunks.
        """
        logger.debug(f"Parsing batch of size {len(batch_data)}.")

        entries = []

        # Unpack document IDs, indices, and chunks for transformation and embedding
        document_ids, page_numbers, chunk_nums, raw_chunks, metadatas = zip(
            *batch_data
        )
        transformed_chunks = self.transform_chunks(raw_chunks, metadatas)
        embedded_chunks = self.embed_chunks(transformed_chunks)

        for (
            document_id,
            page_number,
            chunk_num,
            transformed_chunk,
            embedded_chunk,
            metadata,
        ) in zip(
            document_ids,
            page_numbers,
            chunk_nums,
            transformed_chunks,
            embedded_chunks,
            metadatas,
        ):
            metadata = copy.deepcopy(metadata)
            metadata["pipeline_run_id"] = str(self.pipeline_run_info["run_id"])  # type: ignore
            metadata["text"] = transformed_chunk
            metadata["document_id"] = document_id
            metadata["page_number"] = page_number
            chunk_id = generate_id_from_label(
                f"{document_id}-{page_number}-{chunk_num}"
            )
            entries.append(VectorEntry(chunk_id, embedded_chunk, metadata))
        self.store_chunks(entries, do_upsert)
