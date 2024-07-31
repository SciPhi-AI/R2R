import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Union

from ..abstractions.document import DocumentInfo
from ..abstractions.search import VectorSearchResult
from ..abstractions.user import User, UserCreate, UserResponse
from ..abstractions.vector import VectorEntry
from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class DatabaseConfig(ProviderConfig):
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
        return ["postgres", None]


class VectorDatabaseProvider(Provider, ABC):
    @abstractmethod
    def _initialize_vector_db(self, dimension: int) -> None:
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
        full_text_weight: float = 1.0,
        semantic_weight: float = 1.0,
        rrf_k: int = 20,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        pass

    @abstractmethod
    def create_index(self, index_type, column_name, index_options):
        pass

    @abstractmethod
    def delete_by_metadata(
        self,
        metadata_fields: list[str],
        metadata_values: list[Union[bool, int, str]],
    ) -> list[str]:
        pass

    @abstractmethod
    def get_metadatas(
        self,
        metadata_fields: list[str],
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> list[str]:
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
    def get_document_chunks(self, document_id: str) -> list[dict]:
        pass


class RelationalDatabaseProvider(Provider, ABC):
    @abstractmethod
    def _initialize_relational_db(self) -> None:
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
    def delete_from_documents_overview(
        self, document_id: str, version: Optional[str] = None
    ) -> dict:
        pass

    @abstractmethod
    def get_users_overview(self, user_ids: Optional[list[str]] = None) -> dict:
        pass

    @abstractmethod
    def create_user(self, user: UserCreate) -> User:
        pass

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    def store_verification_code(
        self, user_id: uuid.UUID, verification_code: str, expiry: datetime
    ):
        pass

    @abstractmethod
    def get_user_id_by_verification_code(
        self, verification_code: str
    ) -> Optional[uuid.UUID]:
        pass

    @abstractmethod
    def mark_user_as_verified(self, user_id: uuid.UUID):
        pass

    @abstractmethod
    def mark_user_as_superuser(self, user_id: uuid.UUID):
        pass

    @abstractmethod
    def remove_verification_code(self, verification_code: str):
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        pass

    @abstractmethod
    def update_user(self, user: User) -> User:
        pass

    @abstractmethod
    def delete_user(self, user_id: uuid.UUID):
        pass

    @abstractmethod
    def get_all_users(self) -> list[UserResponse]:
        pass


class DatabaseProvider(Provider):

    def __init__(self, config: DatabaseConfig):
        if not isinstance(config, DatabaseConfig):
            raise ValueError(
                "DatabaseProvider must be initialized with a `DatabaseConfig`."
            )
        logger.info(f"Initializing DatabaseProvider with config {config}.")
        super().__init__(config)
        self.vector: VectorDatabaseProvider = self._initialize_vector_db()
        self.relational: RelationalDatabaseProvider = (
            self._initialize_relational_db()
        )

    @abstractmethod
    def _initialize_vector_db(self) -> VectorDatabaseProvider:
        pass

    @abstractmethod
    def _initialize_relational_db(self) -> RelationalDatabaseProvider:
        pass


# Example usage:
# db_provider = DatabaseProvider(config)
# db_provider.vector.search(...)
# db_provider.relational.get_documents_overview(...)
