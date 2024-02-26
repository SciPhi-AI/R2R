"""
A simple example to demonstrate the usage of `BasicEmbeddingPipeline`.
"""
import copy
import logging
import uuid
from typing import Any, Optional, Tuple, Union

from langchain.text_splitter import TextSplitter

from r2r.core import (
    BasicDocument,
    EmbeddingPipeline,
    LoggingDatabaseConnection,
    VectorDBProvider,
    VectorEntry,
)
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
        logging_provider: Optional[LoggingDatabaseConnection] = None,
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
            logging_provider,
        )
        self.text_splitter = text_splitter
        self.embedding_batch_size = embedding_batch_size
        self.id_prefix = id_prefix
        self.pipeline_run_info = None

    def extract_text(self, document: Any) -> str:
        """
        Extracts text from a document.
        """
        return next(document)[0]

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

    def store_chunks(self, chunks: list[VectorEntry], do_upsert: bool) -> None:
        """
        Stores the embedded chunks in the database, with an option to upsert.
        """
        if do_upsert:
            self.db.upsert_entries(chunks)
        else:
            self.db.copy_entries(chunks)

    def run(
        self,
        document: Union[BasicDocument, list[BasicDocument]],
        do_chunking=False,
        do_upsert=True,
        **kwargs: Any,
    ):
        """
        Executes the embedding pipeline: chunking, transforming, embedding, and storing documents.
        """
        self.initialize_pipeline()
        logger.debug(
            f"Running the `BasicEmbeddingPipeline` with id={self.pipeline_run_info['run_id']}."
        )
        logger.debug(f"Pipeline run type: {self.pipeline_run_info['type']}")

        documents = [document] if not isinstance(document, list) else document
        batch_data = []

        for document in documents:
            chunks = (
                self.chunk_text(document.text)
                if do_chunking
                else [document.text]
            )
            for chunk in chunks:
                batch_data.append(
                    (document.id, chunk, copy.copy(document.metadata))
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
        ids, raw_chunks, metadatas = zip(*batch_data)
        transformed_chunks = self.transform_chunks(raw_chunks, metadatas)
        embedded_chunks = self.embed_chunks(transformed_chunks)

        chunk_count = 0
        for doc_id, transformed_chunk, embedded_chunk, metadata in zip(
            ids, transformed_chunks, embedded_chunks, metadatas
        ):
            metadata = copy.deepcopy(metadata)
            metadata["pipeline_run_id"] = str(self.pipeline_run_info["run_id"])
            metadata["text"] = transformed_chunk
            metadata["document_id"] = doc_id
            chunk_id = uuid.uuid5(
                uuid.NAMESPACE_DNS, f"{doc_id}-{chunk_count}"
            )
            chunk_count += 1
            entries.append(VectorEntry(chunk_id, embedded_chunk, metadata))
        self.store_chunks(entries, do_upsert)
