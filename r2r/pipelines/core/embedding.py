"""
A simple example to demonstrate the usage of `DefaultEmbeddingPipeline`.
"""

import asyncio
import copy
import logging
import uuid
from typing import Any, Generator, Optional, Tuple

from r2r.core import (
    EmbeddingPipeline,
    EmbeddingProvider,
    Extraction,
    Fragment,
    FragmentType,
    LoggingDatabaseConnection,
    Vector,
    VectorDBProvider,
    VectorEntry,
    VectorType,
    log_output_to_db,
)
from r2r.core.utils import TextSplitter, generate_id_from_label
from r2r.embeddings import OpenAIEmbeddingProvider

logger = logging.getLogger(__name__)


class DefaultEmbeddingPipeline(EmbeddingPipeline):
    """
    Embeds and stores documents using a specified embedding model and database.
    """

    def __init__(
        self,
        embedding_provider: OpenAIEmbeddingProvider,
        vector_db_provider: VectorDBProvider,
        text_splitter: TextSplitter,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        embedding_batch_size: int = 1,
        id_prefix: str = "demo",
        *args,
        **kwargs,
    ):
        """
        Initializes the embedding pipeline with necessary components and configurations.
        """
        logger.info(
            f"Initalizing an `DefaultEmbeddingPipeline` to embed and store documents."
        )

        super().__init__(
            embedding_provider,
            vector_db_provider,
            logging_connection,
        )
        self.text_splitter = text_splitter
        self.embedding_batch_size = embedding_batch_size
        self.id_prefix = id_prefix
        self.pipeline_run_info = None

    def initialize_pipeline(self, *args, **kwargs) -> None:
        super().initialize_pipeline(*args, **kwargs)

    def fragment(self, extraction: Extraction) -> list[Fragment]:
        """
        Splits text into manageable chunks for embedding.
        """
        if not isinstance(extraction, Extraction):
            raise ValueError(
                f"Expected an Extraction, but received {type(extraction)}."
            )
        if not isinstance(extraction.data, str):
            raise ValueError(
                f"Expected a string, but received {type(extraction.data)}."
            )
        text_chunks = [
            ele.page_content
            for ele in self.text_splitter.create_documents([extraction.data])
        ]
        fragments = []
        for iteration, chunk in enumerate(text_chunks):
            fragments.append(
                Fragment(
                    id=generate_id_from_label(f"{extraction.id}-{iteration}"),
                    type=FragmentType.TEXT,
                    data=chunk,
                    metadata=copy.deepcopy(extraction.metadata),
                    extraction_id=extraction.id,
                    document_id=extraction.document_id,
                )
            )
        return fragments

    @log_output_to_db
    def transform_fragments(
        self, fragments: list[Fragment], metadatas: list[dict]
    ) -> list[Fragment]:
        """
        Transforms text chunks based on their metadata, e.g., adding prefixes.
        """
        transformed_fragments = []
        for fragment, metadata in zip(fragments, metadatas):
            if "chunk_prefix" in metadata:
                prefix = metadata.pop("chunk_prefix")
                fragment.data = f"{prefix}\n{fragment.data}"
            transformed_fragments.append(fragment)
        return transformed_fragments

    async def embed_fragments(
        self, fragments: list[Fragment]
    ) -> list[list[float]]:
        return await self.embedding_provider.async_get_embeddings(
            [fragment.data for fragment in fragments],
            EmbeddingProvider.PipelineStage.SEARCH,
        )

    async def run(
        self,
        extractions: Generator[Extraction, None, None],
        do_chunking=False,
        do_upsert=True,
        **kwargs: Any,
    ) -> Generator[VectorEntry, None, None]:
        """
        Executes the embedding pipeline: chunking, transforming, embedding, and storing documents.
        """
        self.initialize_pipeline()

        logger.debug(
            f"Running the `DefaultEmbeddingPipeline` asynchronously with pipeline_run_info={self.pipeline_run_info}."
        )
        print("extractions = ", extractions)

        fragment_batch = []
        async for extraction in extractions:
            print("extraction = ", extraction)
            if not isinstance(extraction.data, str):
                raise ValueError(
                    f"Expected a string extraction, but received {type(extraction)}."
                )
            self.log(extraction)
            fragments = self.fragment(extraction)
            print("fragments = ", fragments)

            for fragment in fragments:
                fragment_batch.append(fragment)
                if len(fragment_batch) >= self.embedding_batch_size:
                    vectors = await self.embed_fragments(fragment_batch)
                    for raw_vector, fragment in zip(vectors, fragment_batch):
                        vector = Vector(data=raw_vector)
                        metadata = {
                            "document_id": fragment.document_id,
                            "extraction_id": fragment.extraction_id,
                            **fragment.metadata,
                        }
                        yield VectorEntry(
                            id=fragment.id,
                            vector=vector,
                            metadata=metadata,
                        )
                    fragment_batch = []
        if len(fragment_batch) > 0:
            raw_vectors = self.embed_fragments(fragment_batch)
            for raw_vector, fragment in zip(raw_vectors, fragment_batch):
                vector = Vector(data=raw_vector)
                metadata = {
                    "document_id": fragment.document_id,
                    "extraction_id": fragment.extraction_id,
                    **fragment.metadata,
                }
                yield VectorEntry(
                    id=fragment.id,
                    vector=vector,
                    metadata=metadata,
                )
