from typing import AsyncGenerator, Union

from core.base import ChunkingProvider, Method
from core.base.abstractions.document import DocumentExtraction


class UnstructuredChunkingProvider(ChunkingProvider):
    def __init__(self, config):
        try:
            from unstructured.chunking.basic import chunk_elements

            self.chunk_elements = chunk_elements
            from unstructured.chunking.title import chunk_by_title

            self.chunk_by_title = chunk_by_title

            from unstructured.documents.elements import Text

            self.Text = Text
        except ImportError:
            raise ImportError(
                "Please install the unstructured package to use the unstructured chunking provider."
            )
        super().__init__(config)

    async def chunk(
        self, parsed_document: Union[str, DocumentExtraction]
    ) -> AsyncGenerator[str, None]:

        # as unstructured has already partitioned the document, we can yield the text directly
        if parsed_document.metadata.get("partitioned_by_unstructured", False):
            yield parsed_document.data

        else:
            if self.config.method == Method.BY_TITLE:
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
