import logging
from typing import Any, AsyncGenerator, Union

from core.base import (
    ChunkingProvider,
    R2RChunkingConfig,
    RecursiveCharacterTextSplitter,
    Strategy,
    TextSplitter,
)
from core.base.abstractions.document import DocumentExtraction

logger = logging.getLogger(__name__)


class R2RChunkingProvider(ChunkingProvider):
    def __init__(self, config: R2RChunkingConfig):
        super().__init__(config)
        self.text_splitter = self._initialize_text_splitter()
        logger.info(
            f"R2RChunkingProvider initialized with config: {self.config}"
        )

    def _initialize_text_splitter(self) -> TextSplitter:
        logger.info(
            f"Initializing text splitter with method: {self.config.method}"
        )  # Debug log
        if self.config.method == Strategy.RECURSIVE:
            return RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )
        elif self.config.method == Strategy.CHARACTER:
            from core.base.utils.splitter.text import CharacterTextSplitter

            separator = CharacterTextSplitter.DEFAULT_SEPARATOR
            if self.config.extra_fields:
                separator = self.config.extra_fields.get(
                    "separator", CharacterTextSplitter.DEFAULT_SEPARATOR
                )
            return CharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                separator=separator,
                keep_separator=False,
                strip_whitespace=True,
            )
        elif self.config.method == Strategy.BASIC:
            raise NotImplementedError(
                "Basic chunking method not implemented. Please use Recursive."
            )
        elif self.config.method == Strategy.BY_TITLE:
            raise NotImplementedError("By title method not implemented")
        else:
            raise ValueError(f"Unsupported method type: {self.config.method}")

    def validate(self) -> bool:
        return self.config.chunk_size > 0 and self.config.chunk_overlap >= 0

    def update_config(self, config_override: R2RChunkingConfig):
        if self.config != config_override:
            self.config = config_override
            self.text_splitter = self._initialize_text_splitter()

    async def chunk(
        self, parsed_document: Union[str, DocumentExtraction]
    ) -> AsyncGenerator[Any, None]:

        if isinstance(parsed_document, DocumentExtraction):
            parsed_document = parsed_document.data

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
        self,
        parsed_document: Union[str, DocumentExtraction],
        config_override: R2RChunkingConfig,
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
        config_override: R2RChunkingConfig,
    ) -> "R2RChunkingProvider":
        new_config = R2RChunkingConfig(**original_provider.config.model_dump())
        new_config.update(config_override.model_dump(exclude_unset=True))
        return cls(new_config)
