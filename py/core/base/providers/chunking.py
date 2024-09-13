import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import AsyncGenerator, Optional, Union

from ..abstractions.document import DocumentExtraction
from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class Strategy(str, Enum):
    # Unstructured methods
    BY_TITLE = "by_title"
    BASIC = "basic"
    # R2R methods
    RECURSIVE = "recursive"
    CHARACTER = "character"


class ChunkingConfig(ProviderConfig):
    provider: str = "unstructured_local"

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r", "unstructured_local", "unstructured_api", None]

    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
            },
            "example": {
                "provider": "unstructured_local",
                "strategy": "auto",
                "chunking_strategy": "by_title",
                "new_after_n_chars": 512,
                "max_characters": 1_024,
                "combine_under_n_chars": 128,
                "overlap": 20,
            },
        }


class R2RChunkingConfig(ProviderConfig):
    provider: str = "r2r"
    method: Strategy = Strategy.RECURSIVE
    chunk_size: int = 512
    chunk_overlap: int = 20
    max_chunk_size: Optional[int] = None

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} is not supported.")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r", "unstructured_local", "unstructured_api", None]

    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
                "method": {"type": "string"},
                "chunk_size": {"type": "integer"},
                "chunk_overlap": {"type": "integer"},
                "max_chunk_size": {"type": "integer"},
            },
            "required": ["provider", "method", "chunk_size", "chunk_overlap"],
            "example": {
                "provider": "r2r",
                "method": "recursive",
                "chunk_size": 512,
                "chunk_overlap": 20,
                "max_chunk_size": 1024,
            },
        }


class UnstructuredChunkingConfig(ChunkingConfig):
    provider: str = "unstructured_local"  # or unstructured_api

    combine_under_n_chars: Optional[int] = 128
    max_characters: Optional[int] = 500
    coordinates: bool = False
    encoding: Optional[str] = "utf-8"
    extract_image_block_types: Optional[list[str]] = None
    gz_uncompressed_content_type: Optional[str] = None
    hi_res_model_name: Optional[str] = None
    include_orig_elements: Optional[bool] = True
    include_page_breaks: bool = False

    languages: Optional[list[str]] = None
    multipage_sections: bool = True
    new_after_n_chars: Optional[int] = 1500
    ocr_languages: Optional[list[str]] = None
    output_format: str = "application/json"
    overlap: int = 0
    overlap_all: bool = False
    pdf_infer_table_structure: bool = True

    similarity_threshold: Optional[float] = None
    skip_infer_table_types: Optional[list[str]] = None
    split_pdf_concurrency_level: int = 5
    split_pdf_page: bool = True
    starting_page_number: Optional[int] = None
    strategy: str = "auto"
    chunking_strategy: Strategy = Strategy.BY_TITLE
    unique_element_ids: bool = False
    xml_keep_tags: bool = False

    def validate(self) -> None:
        super().validate()
        if self.strategy not in ["auto", "fast", "hi_res"]:
            raise ValueError("strategy must be 'auto', 'fast', or 'hi_res'")


class ChunkingProvider(Provider, ABC):
    def __init__(self, config: ChunkingConfig):
        super().__init__(config)
        self.config = config

    @abstractmethod
    async def chunk(
        self, parsed_document: Union[str, DocumentExtraction]
    ) -> AsyncGenerator[str, None]:
        """Chunk the parsed document using the configured chunking strategy."""
        pass
