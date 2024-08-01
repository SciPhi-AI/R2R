from typing import Any, AsyncGenerator

from r2r.base import (
    ChunkingConfig,
    ChunkingProvider,
    RecursiveCharacterTextSplitter,
    TextSplitter,
)


class R2RChunkingProvider(ChunkingProvider):
    def __init__(self, config: ChunkingConfig):
        super().__init__(config)
        self.text_splitter = self._initialize_text_splitter()

    def _initialize_text_splitter(self) -> TextSplitter:
        if self.config.method == "recursive":
            return RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )
        else:
            raise ValueError(f"Unsupported method type: {self.config.method}")

    async def chunk(self, parsed_document: Any) -> AsyncGenerator[Any, None]:
        if isinstance(parsed_document, str):
            chunks = self.text_splitter.create_documents([parsed_document])
        else:
            # Assuming parsed_document is already a list of text chunks
            chunks = parsed_document

        for chunk in chunks:
            yield (
                chunk.page_content if hasattr(chunk, "page_content") else chunk
            )
