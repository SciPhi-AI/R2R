from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, List

from pydantic import BaseModel, Field

from ..abstractions.document import Document, DocumentType
from .base import Provider, ProviderConfig


class OverrideParser(BaseModel):
    document_type: DocumentType
    parser: str


class ParsingConfig(ProviderConfig):
    provider = "r2r"
    excluded_parsers: List[DocumentType] = Field(default_factory=list)
    override_parsers: List[OverrideParser] = Field(default_factory=list)

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r", "unstructured", None]


class ParsingProvider(Provider, ABC):
    def __init__(self, config: ParsingConfig):
        super().__init__(config)
        self.config = config

    @abstractmethod
    async def parse(self, document: Document) -> AsyncGenerator[Any, None]:
        """Parse the document using the configured parsing strategy."""
        pass

    @abstractmethod
    def get_parser_for_document_type(self, doc_type: DocumentType) -> str:
        """Get the appropriate parser for a given document type."""
        pass
