from typing import Any, AsyncGenerator

from r2r.base import ChunkingConfig, ChunkingProvider


class R2RChunkingProvider(ChunkingProvider):
    def __init__(self, config: ChunkingConfig):
        super().__init__(config)
        self.text_splitter = None  # Initialize text_splitter as needed

    async def chunk(self, parsed_document: Any) -> AsyncGenerator[Any, None]:
        chunks = self.text_splitter.create_documents([parsed_document])
        for chunk in chunks:
            yield chunk
