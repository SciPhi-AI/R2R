import logging
from abc import ABC, abstractmethod
from typing import Optional, Union

from ..abstractions.document import DocumentInfo
from ..abstractions.search import VectorSearchResult
from ..abstractions.vector import VectorEntry
from .base_provider import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class VectorDBConfig(ProviderConfig):
    provider: str

    def __post_init__(self):
        self.validate()
        # Capture additional fields
        for key, value in self.extra_fields.items():
            setattr(self, key, value)

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["local", "pgvector"]


class VectorDBProvider(Provider, ABC):
    def __init__(self, config: VectorDBConfig):
        if not isinstance(config, VectorDBConfig):
            raise ValueError(
                "VectorDBProvider must be initialized with a `VectorDBConfig`."
            )
        logger.info(f"Initializing VectorDBProvider with config {config}.")
        super().__init__(config)

    @abstractmethod
    def initialize_collection(self, dimension: int) -> None:
        pass

    @abstractmethod
    def copy(self, entry: VectorEntry, commit: bool = True) -> None:
        pass

    @abstractmethod
    def upsert(self, entry: VectorEntry, commit: bool = True) -> None:
        pass

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Union[bool, int, str]] = {},
        limit: int = 10,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        pass

    @abstractmethod
    def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        limit: int = 10,
        filters: Optional[dict[str, Union[bool, int, str]]] = None,
        # Hybrid search parameters
        full_text_weight: float = 1.0,
        semantic_weight: float = 1.0,
        rrf_k: int = 20,  # typical value is ~2x the number of results you want
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        pass

    @abstractmethod
    def create_index(self, index_type, column_name, index_options):
        pass

    def upsert_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        for entry in entries:
            self.upsert(entry, commit=commit)

    def copy_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        for entry in entries:
            self.copy(entry, commit=commit)

    @abstractmethod
    def delete_by_metadata(
        self,
        metadata_fields: list[str],
        metadata_values: list[Union[bool, int, str]],
    ) -> list[str]:
        if len(metadata_fields) != len(metadata_values):
            raise ValueError(
                "The number of metadata fields and values must be equal."
            )
        pass

    @abstractmethod
    def get_metadatas(
        self,
        metadata_fields: list[str],
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> list[str]:
        pass

    @abstractmethod
    def upsert_documents_overview(
        self, document_infs: list[DocumentInfo]
    ) -> None:
        pass

    @abstractmethod
    def get_documents_overview(
        self,
        filter_document_ids: Optional[list[str]] = None,
        filter_user_ids: Optional[list[str]] = None,
    ) -> list[DocumentInfo]:
        pass

    @abstractmethod
    def get_document_chunks(self, document_id: str) -> list[dict]:
        pass

    @abstractmethod
    def delete_documents_overview(self, document_ids: list[str]) -> dict:
        pass

    @abstractmethod
    def get_users_overview(self, user_ids: Optional[list[str]] = None) -> dict:
        pass
