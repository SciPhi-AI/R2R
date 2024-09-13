import logging
from typing import AsyncGenerator, Union

from core.base import ChunkingProvider, Strategy, UnstructuredChunkingConfig
from core.base.abstractions.document import DocumentExtraction

logger = logging.getLogger(__name__)


class UnstructuredChunkingProvider(ChunkingProvider):
    def __init__(self, config: UnstructuredChunkingConfig):
        try:
            from unstructured.chunking.basic import chunk_elements
            from unstructured.chunking.title import chunk_by_title
            from unstructured.documents.elements import Text

            self.chunk_by_title = chunk_by_title
            self.chunk_elements = chunk_elements
            self.Text = Text

        except ImportError:
            self.chunk_elements = None
            self.chunk_by_title = None
            self.Text = None

        super().__init__(config)

    async def chunk(
        self, parsed_document: Union[str, DocumentExtraction]
    ) -> AsyncGenerator[str, None]:

        # as unstructured has already partitioned the document, we can yield the text directly
        if parsed_document.metadata.get("partitioned_by_unstructured", False):
            yield parsed_document.data

        else:

            try:
                if self.config.strategy == Strategy.BY_TITLE:
                    chunks = self.chunk_by_title(
                        [self.Text(text=parsed_document.data)],
                        max_characters=self.config.chunk_size,
                        new_after_n_chars=self.config.max_chunk_size
                        or self.config.chunk_size,
                        overlap=self.config.chunk_overlap,
                    )
                else:
                    chunks = self.chunk_elements(
                        [self.Text(text=parsed_document.data)],
                        max_characters=self.config.chunk_size,
                        new_after_n_chars=self.config.max_chunk_size
                        or self.config.chunk_size,
                        overlap=self.config.chunk_overlap,
                    )
                for chunk in chunks:
                    yield chunk.text

            except Exception as e:
                logger.error(
                    f"If you are trying to use r2r for parsing and unstructured for chunking, please use the r2r-unstructured docker. You can do that using --docker flag with `r2r serve` command. Error: {e}"
                )
                raise e
