"""
A simple example to demonstrate the usage of `DefaultEmbeddingPipe`.
"""

import asyncio
import copy
import logging
from abc import abstractmethod
from typing import Any, AsyncGenerator, Optional

from r2r.core import (
    EmbeddingProvider,
    Extraction,
    Fragment,
    FragmentType,
    LoggingDatabaseConnection,
    PipeType,
    TextSplitter,
    Vector,
    VectorEntry,
    generate_id_from_label,
    log_output_to_db,
)
from r2r.embeddings import OpenAIEmbeddingProvider

from ..abstractions.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class EmbeddingPipe(LoggableAsyncPipe):
    INPUT_TYPE = AsyncGenerator[Extraction, None]
    OUTPUT_TYPE = AsyncGenerator[VectorEntry, None]

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.embedding_provider = embedding_provider
        super().__init__(logging_connection=logging_connection, **kwargs)

    @property
    def type(self) -> PipeType:
        return PipeType.EMBEDDING

    @abstractmethod
    async def fragment(
        self, extraction: Extraction
    ) -> AsyncGenerator[Fragment, None]:
        pass

    @abstractmethod
    async def transform_fragments(
        self, fragments: list[Fragment], metadatas: list[dict]
    ) -> AsyncGenerator[Fragment, None]:
        pass

    @abstractmethod
    async def embed(self, fragments: list[Fragment]) -> list[list[float]]:
        pass

    @abstractmethod
    async def run(self, input: INPUT_TYPE, **kwargs) -> OUTPUT_TYPE:
        pass


class DefaultEmbeddingPipe(EmbeddingPipe):
    """
    Embeds and stores documents using a specified embedding model and database.
    """

    def __init__(
        self,
        embedding_provider: OpenAIEmbeddingProvider,
        text_splitter: TextSplitter,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        embedding_batch_size: int = 1,
        id_prefix: str = "demo",
        *args,
        **kwargs,
    ):
        """
        Initializes the embedding pipe with necessary components and configurations.
        """
        logger.info(
            f"Initalizing an `DefaultEmbeddingPipe` to embed and store documents."
        )

        super().__init__(
            embedding_provider,
            logging_connection,
        )
        self.text_splitter = text_splitter
        self.embedding_batch_size = embedding_batch_size
        self.id_prefix = id_prefix
        self.pipe_run_info = None

    async def fragment(
        self, extraction: Extraction
    ) -> AsyncGenerator[Fragment, None]:
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
        for iteration, chunk in enumerate(text_chunks):
            yield Fragment(
                id=generate_id_from_label(f"{extraction.id}-{iteration}"),
                type=FragmentType.TEXT,
                data=chunk,
                metadata=copy.deepcopy(extraction.metadata),
                extraction_id=extraction.id,
                document_id=extraction.document_id,
            )

    @log_output_to_db
    async def transform_fragments(
        self, fragments: list[Fragment], metadatas: list[dict]
    ) -> AsyncGenerator[Fragment, None]:
        """
        Transforms text chunks based on their metadata, e.g., adding prefixes.
        """
        async for fragment, metadata in zip(fragments, metadatas):
            if "chunk_prefix" in metadata:
                prefix = metadata.pop("chunk_prefix")
                fragment.data = f"{prefix}\n{fragment.data}"
            yield fragment

    async def embed(self, fragments: list[Fragment]) -> list[float]:
        return await self.embedding_provider.async_get_embeddings(
            [fragment.data for fragment in fragments],
            EmbeddingProvider.PipeStage.SEARCH,
        )

    async def run(
        self,
        input: AsyncGenerator[Extraction, None],
        **kwargs: Any,
    ) -> AsyncGenerator[VectorEntry, None]:
        """
        Executes the embedding pipe: chunking, transforming, embedding, and storing documents.
        """
        self._initialize_pipe()

        batch_tasks = []
        fragment_batch = []

        async for extraction in input:
            async for fragment in self.fragment(extraction):
                fragment_batch.append(fragment)
                if len(fragment_batch) >= self.embedding_batch_size:
                    # Here, ensure `_process_batch` is scheduled as a coroutine, not called directly
                    batch_tasks.append(
                        self._process_batch(fragment_batch.copy())
                    )  # pass a copy if necessary
                    fragment_batch.clear()  # Clear the batch for new fragments

        if fragment_batch:  # Process any remaining fragments
            batch_tasks.append(self._process_batch(fragment_batch.copy()))

        # Process tasks as they complete
        for task in asyncio.as_completed(batch_tasks):
            batch_result = await task  # Wait for the next task to complete
            for vector_entry in batch_result:
                yield vector_entry

    async def _process_batch(
        self, fragment_batch: list[Fragment]
    ) -> list[VectorEntry]:
        """
        Embeds a batch of fragments and yields vector entries.
        """
        vectors = await self.embed(fragment_batch)
        return [
            VectorEntry(
                id=fragment.id,
                vector=Vector(data=raw_vector),
                metadata={
                    "document_id": fragment.document_id,
                    "extraction_id": fragment.extraction_id,
                    "text": fragment.data,
                    **fragment.metadata,
                },
            )
            for raw_vector, fragment in zip(vectors, fragment_batch)
        ]
