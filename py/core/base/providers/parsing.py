from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from pydantic import BaseModel, Field

from ..abstractions.document import Document, DocumentType
from .base import Provider, ProviderConfig
from .chunking import ChunkingConfig


class OverrideParser(BaseModel):
    document_type: DocumentType
    parser: str


class ParsingConfig(ProviderConfig):
    provider: str = "r2r"
    excluded_parsers: list[DocumentType] = Field(default_factory=list)
    override_parsers: list[OverrideParser] = Field(default_factory=list)
    chunking_config: ChunkingConfig = Field(default_factory=ChunkingConfig)

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r", "unstructured_local", "unstructured_api", None]

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} is not supported.")


class ParsingProvider(Provider, ABC):
    def __init__(self, config: ParsingConfig):
        super().__init__(config)
        self.config = config

    @abstractmethod
    async def parse(
        self, file_content: bytes, document: Document
    ) -> AsyncGenerator[Any, None]:
        """Parse the document using the configured parsing strategy."""
        pass

    @abstractmethod
    def get_parser_for_document_type(self, doc_type: DocumentType) -> str:
        """Get the appropriate parser for a given document type."""
        pass
