from abc import ABC, abstractmethod
from typing import Optional, Union

from ..abstractions.search import SearchResult
from ..abstractions.vector import VectorEntry
from .base import Provider, ProviderConfig


class VectorDBConfig(ProviderConfig):
    provider: str
    collection_name: str

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
        return ["local", "pgvector", "qdrant"]


class VectorDBProvider(Provider, ABC):
    def __init__(self, config: VectorDBConfig):
        if not isinstance(config, VectorDBConfig):
            raise ValueError(
                "VectorDBProvider must be initialized with a `VectorDBConfig`."
            )

        super().__init__(config)

    @abstractmethod
    def initialize_collection(
        self, dimension: int
    ) -> None:
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
    ) -> list[SearchResult]:
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
        self, metadata_field: str, metadata_value: Union[bool, int, str]
    ) -> None:
        pass

    @abstractmethod
    def get_metadatas(
        self,
        metadata_fields: list[str],
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> list[str]:
        pass
