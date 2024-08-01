from typing import Any, AsyncGenerator

from unstructured.chunking.basic import chunk_elements
from unstructured.chunking.title import chunk_by_title

from r2r.base import ChunkingProvider


class UnstructuredChunkingProvider(ChunkingProvider):
    async def chunk(self, parsed_document: Any) -> AsyncGenerator[Any, None]:
        if self.config.unstructured_method == "by_title":
            chunks = chunk_by_title(
                parsed_document,
                max_characters=self.config.chunk_size,
                new_after_n_chars=self.config.max_chunk_size
                or self.config.chunk_size,
                overlap=self.config.overlap,
            )
        else:
            chunks = chunk_elements(
                parsed_document,
                max_characters=self.config.chunk_size,
                new_after_n_chars=self.config.max_chunk_size
                or self.config.chunk_size,
                overlap=self.config.overlap,
            )
        for chunk in chunks:
            yield chunk
