from typing import Any, AsyncGenerator

from r2r.base import (
    ChunkingConfig,
    ChunkingProvider,
    Method,
    RecursiveCharacterTextSplitter,
    TextSplitter,
)


class R2RChunkingProvider(ChunkingProvider):
    def __init__(self, config: ChunkingConfig):
        super().__init__(config)
        self.text_splitter = self._initialize_text_splitter()
        print(
            f"R2RChunkingProvider initialized with config: {self.config}"
        )  # Debug log

    def _initialize_text_splitter(self) -> TextSplitter:
        print(
            f"Initializing text splitter with method: {self.config.method}"
        )  # Debug log
        if self.config.method == Method.RECURSIVE:
            return RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )
        elif self.config.method == Method.BASIC:
            # Implement basic method
            raise NotImplementedError("Basic method not implemented yet")
        elif self.config.method == Method.BY_TITLE:
            # Implement by_title method
            raise NotImplementedError("By_title method not implemented yet")
        else:
            raise ValueError(f"Unsupported method type: {self.config.method}")

    def validate(self) -> bool:
        return self.config.chunk_size > 0 and self.config.chunk_overlap >= 0

    def update_config(self, config_override: ChunkingConfig):
        if self.config != config_override:
            self.config = config_override
            self.text_splitter = self._initialize_text_splitter()

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

    async def chunk_with_override(
        self, parsed_document: Any, config_override: ChunkingConfig
    ) -> AsyncGenerator[Any, None]:
        original_config = self.config
        original_splitter = self.text_splitter
        try:
            self.update_config(config_override)
            async for chunk in self.chunk(parsed_document):
                yield chunk
        finally:
            self.config = original_config
            self.text_splitter = original_splitter

    @classmethod
    def with_override(
        cls,
        original_provider: "R2RChunkingProvider",
        config_override: ChunkingConfig,
    ) -> "R2RChunkingProvider":
        new_config = ChunkingConfig(**original_provider.config.model_dump())
        new_config.update(config_override.model_dump(exclude_unset=True))
        return cls(new_config)
