from typing import Any, AsyncGenerator

from r2r.base import ChunkingProvider


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

    async def chunk(self, parsed_document: str) -> AsyncGenerator[str, None]:
        if self.config.method == "by_title":
            chunks = self.chunk_by_title(
                [self.Text(text=parsed_document)],
                max_characters=self.config.chunk_size,
                new_after_n_chars=self.config.max_chunk_size
                or self.config.chunk_size,
                overlap=self.config.chunk_overlap,
            )
        else:
            chunks = self.chunk_elements(
                [self.Text(text=parsed_document)],
                max_characters=self.config.chunk_size,
                new_after_n_chars=self.config.max_chunk_size
                or self.config.chunk_size,
                overlap=self.config.chunk_overlap,
            )
        for chunk in chunks:
            yield chunk.text
