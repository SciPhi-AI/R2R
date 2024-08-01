from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncGenerator, List, Optional

from pydantic import BaseModel, Field

from ..abstractions.document import Document, DocumentType
from .base import Provider, ProviderConfig


class Method(str, Enum):
    BY_TITLE = "by_title"
    BASIC = "basic"
    RECURSIVE = "recursive"


class TextSplitterConfig(BaseModel):
    type: str = "recursive_character"
    chunk_size: int = 512
    chunk_overlap: int = 20
    hard_max: Optional[int] = None


class ChunkingConfig(ProviderConfig):
    provider = "r2r"
    method: Method = Method.RECURSIVE
    text_splitter: TextSplitterConfig = Field(
        default_factory=TextSplitterConfig
    )

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r", "unstructured", None]


class ChunkingProvider(Provider, ABC):
    def __init__(self, config: ChunkingConfig):
        super().__init__(config)
        self.config = config

    @abstractmethod
    async def chunk(self, parsed_document: Any) -> AsyncGenerator[Any, None]:
        """Chunk the parsed document using the configured chunking strategy."""
        pass
