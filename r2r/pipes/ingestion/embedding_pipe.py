import copy
import logging
import uuid
from typing import Any, AsyncGenerator, Optional, Union

from r2r.base import (
    AsyncState,
    EmbeddingProvider,
    Extraction,
    Fragment,
    FragmentType,
    KVLoggingSingleton,
    PipeType,
    R2RDocumentProcessingError,
    TextSplitter,
    Vector,
    VectorEntry,
    generate_id_from_label,
)
from r2r.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class EmbeddingPipe(AsyncPipe):
    """
    Embeds and stores documents using a specified embedding model and database.
    """

    class Input(AsyncPipe.Input):
        message: AsyncGenerator[
            Union[Extraction, R2RDocumentProcessingError], None
        ]

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        text_splitter: TextSplitter,
        embedding_batch_size: int = 1,
        id_prefix: str = "demo",
        pipe_logger: Optional[KVLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config
            or AsyncPipe.PipeConfig(name="default_embedding_pipe"),
        )
        self.embedding_provider = embedding_provider
        self.text_splitter = text_splitter
        self.embedding_batch_size = embedding_batch_size
        self.id_prefix = id_prefix
        self.pipe_run_info = None

    async def fragment(
        self, extraction: Extraction, run_id: uuid.UUID
    ) -> AsyncGenerator[Fragment, None]:
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
            fragment = Fragment(
                id=generate_id_from_label(f"{extraction.id}-{iteration}"),
                type=FragmentType.TEXT,
                data=chunk,
                metadata=copy.deepcopy(extraction.metadata),
                extraction_id=extraction.id,
                document_id=extraction.document_id,
            )
            yield fragment
            iteration += 1

    async def embed(self, fragments: list[Fragment]) -> list[float]:
        return await self.embedding_provider.async_get_embeddings(
            [fragment.data for fragment in fragments],
            EmbeddingProvider.PipeStage.BASE,
        )

    async def _process_batch(
        self, fragment_batch: list[Fragment]
    ) -> list[VectorEntry]:
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

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: uuid.UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[R2RDocumentProcessingError, VectorEntry], None]:
        fragment_info = {}
        async for extraction in input.message:
            if isinstance(extraction, R2RDocumentProcessingError):
                yield extraction
                continue

            fragment_batch = []
            async for fragment in self.fragment(extraction, run_id):
                if extraction.document_id in fragment_info:
                    fragment_info[extraction.document_id] += 1
                else:
                    fragment_info[extraction.document_id] = 0
                fragment.metadata["chunk_order"] = fragment_info[
                    extraction.document_id
                ]

                version = fragment.metadata.get("version", "v0")
                if not fragment.id:
                    fragment.id = generate_id_from_label(
                        f"{extraction.id}-{fragment_info[extraction.document_id]}-{version}"
                    )

                fragment_batch.append(fragment)
                if len(fragment_batch) >= self.embedding_batch_size:
                    try:
                        batch_result = await self._process_batch(
                            fragment_batch
                        )
                        for vector_entry in batch_result:
                            yield vector_entry
                    except Exception as e:
                        logger.error(f"Error processing batch: {e}")
                        yield R2RDocumentProcessingError(
                            str(e), extraction.document_id
                        )
                    fragment_batch.clear()

            if fragment_batch:
                try:
                    batch_result = await self._process_batch(fragment_batch)
                    for vector_entry in batch_result:
                        yield vector_entry
                except Exception as e:
                    logger.error(f"Error processing batch: {e}")
                    yield R2RDocumentProcessingError(
                        str(e), extraction.document_id
                    )

        logger.debug(
            f"Fragmented the input document ids into counts as shown: {fragment_info}"
        )
