import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Union
from uuid import UUID

from ..abstractions import DocumentInfo, VectorEntry, VectorSearchResult
from ..api.models import UserResponse
from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)

VectorDBFilterValue = Union[str, UUID]


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


class VectorDBProvider(Provider, ABC):
    @abstractmethod
    def _initialize_vector_db(self, dimension: int) -> None:
        pass

    @abstractmethod
    def create_index(self, index_type, column_name, index_options):
        pass

    @abstractmethod
    def upsert(self, entry: VectorEntry, commit: bool = True) -> None:
        pass

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        filters: dict[str, VectorDBFilterValue] = {},
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
        filters: Optional[dict[str, VectorDBFilterValue]] = None,
        full_text_weight: float = 1.0,
        semantic_weight: float = 1.0,
        rrf_k: int = 20,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        pass

    @abstractmethod
    def delete(self, filters: dict[str, VectorDBFilterValue]) -> list[str]:
        pass


class RelationalDBProvider(Provider, ABC):
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
        filter_user_ids: Optional[str] = None,
        filter_group_ids: Optional[list[str]] = None,
        filter_document_ids: Optional[list[str]] = None,
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
    def create_user(self, email: str, password: str) -> UserResponse:
        pass

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        pass

    @abstractmethod
    def store_verification_code(
        self, user_id: UUID, verification_code: str, expiry: datetime
    ):
        pass

    @abstractmethod
    def get_user_id_by_verification_code(
        self, verification_code: str
    ) -> Optional[UUID]:
        pass

    @abstractmethod
    def mark_user_as_verified(self, user_id: UUID):
        pass

    @abstractmethod
    def mark_user_as_superuser(self, user_id: UUID):
        pass

    @abstractmethod
    def remove_verification_code(self, verification_code: str):
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: UUID) -> Optional[UserResponse]:
        pass

    @abstractmethod
    def update_user(
        self,
        user_id: UUID,
        email: Optional[str],
        name: Optional[str],
        bio: Optional[str],
        profile_picture: Optional[str],
    ) -> UserResponse:
        pass

    @abstractmethod
    def delete_user(self, user_id: UUID):
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
        self.vector: VectorDBProvider = self._initialize_vector_db()
        self.relational: RelationalDBProvider = (
            self._initialize_relational_db()
        )

    @abstractmethod
    def _initialize_vector_db(self) -> VectorDBProvider:
        pass

    @abstractmethod
    def _initialize_relational_db(self) -> RelationalDBProvider:
        pass
