from typing import Any, AsyncGenerator

from r2r.base import ChunkingProvider


class UnstructuredChunkingProvider(ChunkingProvider):
    def __init__(self, config):
        try:
            from unstructured.chunking.basic import chunk_elements

            self.chunk_elements = chunk_elements
            from unstructured.chunking.title import chunk_by_title

            self.chunk_by_title = chunk_by_title
        except ImportError:
            raise ImportError(
                "Please install the unstructured package to use the unstructured chunking provider."
            )
        super().__init__(config)

    async def chunk(self, parsed_document: Any) -> AsyncGenerator[Any, None]:
        if self.config.unstructured_method == "by_title":
            chunks = self.chunk_by_title(
                parsed_document,
                max_characters=self.config.chunk_size,
                new_after_n_chars=self.config.max_chunk_size
                or self.config.chunk_size,
                overlap=self.config.overlap,
            )
        else:
            chunks = self.chunk_elements(
                parsed_document,
                max_characters=self.config.chunk_size,
                new_after_n_chars=self.config.max_chunk_size
                or self.config.chunk_size,
                overlap=self.config.overlap,
            )
        for chunk in chunks:
            yield chunk
