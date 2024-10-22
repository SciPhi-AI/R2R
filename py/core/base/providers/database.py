import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional, Sequence, Tuple, Union
from uuid import UUID

from pydantic import BaseModel

from core.base import VectorEntry
from core.base.abstractions import (
    DocumentInfo,
    UserStats,
    VectorEntry,
    VectorSearchResult,
    VectorSearchSettings,
)
from core.base.api.models import (
    CollectionOverviewResponse,
    CollectionResponse,
    UserResponse,
)
from shared.abstractions.vector import (
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
    VectorTableName,
)

from .base import Provider, ProviderConfig

logger = logging.getLogger()
from shared.utils import _decorate_vector_type

logger = logging.getLogger()


class PostgresConfigurationSettings(BaseModel):
    """
    Configuration settings with defaults defined by the PGVector docker image.

    These settings are helpful in managing the connections to the database.
    To tune these settings for a specific deployment, see https://pgtune.leopard.in.ua/
    """

    max_connections: Optional[int] = 256
    shared_buffers: Optional[int] = 16384
    effective_cache_size: Optional[int] = 524288
    maintenance_work_mem: Optional[int] = 65536
    checkpoint_completion_target: Optional[float] = 0.9
    wal_buffers: Optional[int] = 512
    default_statistics_target: Optional[int] = 100
    random_page_cost: Optional[float] = 4
    effective_io_concurrency: Optional[int] = 1
    work_mem: Optional[int] = 4096
    huge_pages: Optional[str] = "try"
    min_wal_size: Optional[int] = 80
    max_wal_size: Optional[int] = 1024
    max_worker_processes: Optional[int] = 8
    max_parallel_workers_per_gather: Optional[int] = 2
    max_parallel_workers: Optional[int] = 8
    max_parallel_maintenance_workers: Optional[int] = 2


class DatabaseConfig(ProviderConfig):
    """A base database configuration class"""

    provider: str = "postgres"
    user: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    db_name: Optional[str] = None
    project_name: Optional[str] = None
    postgres_configuration_settings: Optional[
        PostgresConfigurationSettings
    ] = None
    default_collection_name: str = "Default"
    default_collection_description: str = "Your default collection."
    enable_fts: bool = False

    def __post_init__(self):
        self.validate_config()
        # Capture additional fields
        for key, value in self.extra_fields.items():
            setattr(self, key, value)

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["postgres"]


class DatabaseConnectionManager(ABC):
    @abstractmethod
    def execute_query(
        self,
        query: str,
        params: Optional[Union[dict[str, Any], Sequence[Any]]] = None,
        isolation_level: Optional[str] = None,
    ):
        pass

    @abstractmethod
    async def execute_many(self, query, params=None, batch_size=1000):
        pass

    @abstractmethod
    def fetch_query(
        self,
        query: str,
        params: Optional[Union[dict[str, Any], Sequence[Any]]] = None,
    ):
        pass

    @abstractmethod
    def fetchrow_query(
        self,
        query: str,
        params: Optional[Union[dict[str, Any], Sequence[Any]]] = None,
    ):
        pass

    @abstractmethod
    async def initialize(self, pool: Any):
        pass


class Handler(ABC):
    def __init__(
        self, project_name: str, connection_manager: DatabaseConnectionManager
    ):
        self.project_name = project_name
        self.connection_manager = connection_manager

    def _get_table_name(self, base_name: str) -> str:
        return f"{self.project_name}.{base_name}"

    @abstractmethod
    def create_table(self):
        pass


class DocumentHandler(Handler):

    @abstractmethod
    async def upsert_documents_overview(
        self, documents_overview: Union[DocumentInfo, list[DocumentInfo]]
    ) -> None:
        pass

    @abstractmethod
    async def delete_from_documents_overview(
        self, document_id: UUID, version: Optional[str] = None
    ) -> None:
        pass

    @abstractmethod
    async def get_documents_overview(
        self,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = -1,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def get_workflow_status(
        self, id: Union[UUID, list[UUID]], status_type: str
    ):
        pass

    @abstractmethod
    async def set_workflow_status(
        self, id: Union[UUID, list[UUID]], status_type: str, status: str
    ):
        pass

    @abstractmethod
    async def get_document_ids_by_status(
        self,
        status_type: str,
        status: Union[str, list[str]],
        collection_id: Optional[UUID] = None,
    ):
        pass


class CollectionHandler(Handler):
    @abstractmethod
    async def create_default_collection(
        self, user_id: Optional[UUID] = None
    ) -> CollectionResponse:
        pass

    @abstractmethod
    async def collection_exists(self, collection_id: UUID) -> bool:
        pass

    @abstractmethod
    async def create_collection(
        self,
        name: str,
        description: str = "",
        collection_id: Optional[UUID] = None,
    ) -> CollectionResponse:
        pass

    @abstractmethod
    async def get_collection(self, collection_id: UUID) -> CollectionResponse:
        pass

    @abstractmethod
    async def update_collection(
        self,
        collection_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> CollectionResponse:
        pass

    @abstractmethod
    async def delete_collection_relational(self, collection_id: UUID) -> None:
        pass

    @abstractmethod
    async def list_collections(
        self, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[CollectionResponse], int]]:
        """List collections with pagination."""
        pass

    @abstractmethod
    async def get_collections_by_ids(
        self, collection_ids: list[UUID]
    ) -> list[CollectionResponse]:
        pass

    @abstractmethod
    async def documents_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[DocumentInfo], int]]:
        pass

    @abstractmethod
    async def get_collections_overview(
        self,
        collection_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = -1,
    ) -> dict[str, Union[list[CollectionOverviewResponse], int]]:
        pass

    @abstractmethod
    async def get_collections_for_user(
        self, user_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[CollectionResponse], int]]:
        pass

    @abstractmethod
    async def assign_document_to_collection_relational(
        self,
        document_id: UUID,
        collection_id: UUID,
    ) -> UUID:
        pass

    @abstractmethod
    async def document_collections(
        self, document_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[CollectionResponse], int]]:
        pass

    @abstractmethod
    async def remove_document_from_collection_relational(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        pass


class TokenHandler(Handler):

    @abstractmethod
    async def create_table(self):
        pass

    @abstractmethod
    async def blacklist_token(
        self, token: str, current_time: Optional[datetime] = None
    ):
        pass

    @abstractmethod
    async def is_token_blacklisted(self, token: str) -> bool:
        pass

    @abstractmethod
    async def clean_expired_blacklisted_tokens(
        self,
        max_age_hours: int = 7 * 24,
        current_time: Optional[datetime] = None,
    ):
        pass


class UserHandler(Handler):
    TABLE_NAME = "users"

    @abstractmethod
    async def get_user_by_id(self, user_id: UUID) -> UserResponse:
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> UserResponse:
        pass

    @abstractmethod
    async def create_user(self, email: str, password: str) -> UserResponse:
        pass

    @abstractmethod
    async def update_user(self, user: UserResponse) -> UserResponse:
        pass

    @abstractmethod
    async def delete_user_relational(self, user_id: UUID) -> None:
        pass

    @abstractmethod
    async def update_user_password(
        self, user_id: UUID, new_hashed_password: str
    ):
        pass

    @abstractmethod
    async def get_all_users(self) -> list[UserResponse]:
        pass

    @abstractmethod
    async def store_verification_code(
        self, user_id: UUID, verification_code: str, expiry: datetime
    ):
        pass

    @abstractmethod
    async def verify_user(self, verification_code: str) -> None:
        pass

    @abstractmethod
    async def remove_verification_code(self, verification_code: str):
        pass

    @abstractmethod
    async def expire_verification_code(self, user_id: UUID):
        pass

    @abstractmethod
    async def store_reset_token(
        self, user_id: UUID, reset_token: str, expiry: datetime
    ):
        pass

    @abstractmethod
    async def get_user_id_by_reset_token(
        self, reset_token: str
    ) -> Optional[UUID]:
        pass

    @abstractmethod
    async def remove_reset_token(self, user_id: UUID):
        pass

    @abstractmethod
    async def remove_user_from_all_collections(self, user_id: UUID):
        pass

    @abstractmethod
    async def add_user_to_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> None:
        pass

    @abstractmethod
    async def remove_user_from_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> None:
        pass

    @abstractmethod
    async def get_users_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[UserResponse], int]]:
        pass

    @abstractmethod
    async def mark_user_as_superuser(self, user_id: UUID):
        pass

    @abstractmethod
    async def get_user_id_by_verification_code(
        self, verification_code: str
    ) -> Optional[UUID]:
        pass

    @abstractmethod
    async def mark_user_as_verified(self, user_id: UUID):
        pass

    @abstractmethod
    async def get_users_overview(
        self,
        user_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = -1,
    ) -> dict[str, Union[list[UserStats], int]]:
        pass


class VectorHandler(Handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    async def upsert(self, entry: VectorEntry) -> None:
        pass

    @abstractmethod
    async def upsert_entries(self, entries: list[VectorEntry]) -> None:
        pass

    @abstractmethod
    async def semantic_search(
        self, query_vector: list[float], search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        pass

    @abstractmethod
    async def full_text_search(
        self, query_text: str, search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        pass

    @abstractmethod
    async def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        search_settings: VectorSearchSettings,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        pass

    @abstractmethod
    async def delete(
        self, filters: dict[str, Any]
    ) -> dict[str, dict[str, str]]:
        pass

    @abstractmethod
    async def assign_document_to_collection_vector(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        pass

    @abstractmethod
    async def remove_document_from_collection_vector(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        pass

    @abstractmethod
    async def delete_user_vector(self, user_id: UUID) -> None:
        pass

    @abstractmethod
    async def delete_collection_vector(self, collection_id: UUID) -> None:
        pass

    @abstractmethod
    async def get_document_chunks(
        self,
        document_id: UUID,
        offset: int = 0,
        limit: int = -1,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def create_index(
        self,
        table_name: Optional[VectorTableName] = None,
        index_measure: IndexMeasure = IndexMeasure.cosine_distance,
        index_method: IndexMethod = IndexMethod.auto,
        index_arguments: Optional[
            Union[IndexArgsIVFFlat, IndexArgsHNSW]
        ] = None,
        index_name: Optional[str] = None,
        concurrently: bool = True,
    ) -> None:
        pass

    @abstractmethod
    async def list_indices(
        self, table_name: Optional[VectorTableName] = None
    ) -> list[dict]:
        pass

    @abstractmethod
    async def delete_index(
        self,
        index_name: str,
        table_name: Optional[VectorTableName] = None,
        concurrently: bool = True,
    ) -> None:
        pass

    @abstractmethod
    async def select_index(
        self, index_name: str, table_name: Optional[VectorTableName] = None
    ) -> None:
        pass

    @abstractmethod
    async def get_semantic_neighbors(
        self,
        document_id: UUID,
        chunk_id: UUID,
        limit: int = 10,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        pass


class DatabaseProvider(Provider):
    connection_manager: DatabaseConnectionManager
    document_handler: DocumentHandler
    collection_handler: CollectionHandler
    token_handler: TokenHandler
    user_handler: UserHandler
    vector_handler: VectorHandler
    config: DatabaseConfig
    project_name: str

    def __init__(self, config: DatabaseConfig):
        logger.info(f"Initializing DatabaseProvider with config {config}.")
        super().__init__(config)

    @abstractmethod
    async def __aenter__(self):
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb):
        pass

    # Document handler methods
    async def upsert_documents_overview(
        self, documents_overview: Union[DocumentInfo, list[DocumentInfo]]
    ) -> None:
        return await self.document_handler.upsert_documents_overview(
            documents_overview
        )

    async def delete_from_documents_overview(
        self, document_id: UUID, version: Optional[str] = None
    ) -> None:
        return await self.document_handler.delete_from_documents_overview(
            document_id, version
        )

    async def get_documents_overview(
        self,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = -1,
    ) -> dict[str, Any]:
        return await self.document_handler.get_documents_overview(
            filter_user_ids,
            filter_document_ids,
            filter_collection_ids,
            offset,
            limit,
        )

    async def get_workflow_status(
        self, id: Union[UUID, list[UUID]], status_type: str
    ):
        return await self.document_handler.get_workflow_status(id, status_type)

    async def set_workflow_status(
        self, id: Union[UUID, list[UUID]], status_type: str, status: str
    ):
        return await self.document_handler.set_workflow_status(
            id, status_type, status
        )

    async def get_document_ids_by_status(
        self,
        status_type: str,
        status: Union[str, list[str]],
        collection_id: Optional[UUID] = None,
    ):
        return await self.document_handler.get_document_ids_by_status(
            status_type, status, collection_id
        )

    # Collection handler methods
    async def create_default_collection(
        self, user_id: Optional[UUID] = None
    ) -> CollectionResponse:
        return await self.collection_handler.create_default_collection(user_id)

    async def collection_exists(self, collection_id: UUID) -> bool:
        return await self.collection_handler.collection_exists(collection_id)

    async def create_collection(
        self,
        name: str,
        description: str = "",
        collection_id: Optional[UUID] = None,
    ) -> CollectionResponse:
        return await self.collection_handler.create_collection(
            name, description, collection_id
        )

    async def get_collection(self, collection_id: UUID) -> CollectionResponse:
        return await self.collection_handler.get_collection(collection_id)

    async def update_collection(
        self,
        collection_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> CollectionResponse:
        return await self.collection_handler.update_collection(
            collection_id, name, description
        )

    async def delete_collection_relational(self, collection_id: UUID) -> None:
        return await self.collection_handler.delete_collection_relational(
            collection_id
        )

    async def list_collections(
        self, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[CollectionResponse], int]]:
        return await self.collection_handler.list_collections(offset, limit)

    async def get_collections_by_ids(
        self, collection_ids: list[UUID]
    ) -> list[CollectionResponse]:
        return await self.collection_handler.get_collections_by_ids(
            collection_ids
        )

    async def documents_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[DocumentInfo], int]]:
        return await self.collection_handler.documents_in_collection(
            collection_id, offset, limit
        )

    async def get_collections_overview(
        self,
        collection_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = -1,
    ) -> dict[str, Union[list[CollectionOverviewResponse], int]]:
        return await self.collection_handler.get_collections_overview(
            collection_ids, offset, limit
        )

    async def get_collections_for_user(
        self, user_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[CollectionResponse], int]]:
        return await self.collection_handler.get_collections_for_user(
            user_id, offset, limit
        )

    async def assign_document_to_collection_relational(
        self,
        document_id: UUID,
        collection_id: UUID,
    ) -> UUID:
        return await self.collection_handler.assign_document_to_collection_relational(
            document_id, collection_id
        )

    async def document_collections(
        self, document_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[CollectionResponse], int]]:
        return await self.collection_handler.document_collections(
            document_id, offset, limit
        )

    async def remove_document_from_collection_relational(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        return await self.collection_handler.remove_document_from_collection_relational(
            document_id, collection_id
        )

    # Token handler methods
    async def blacklist_token(
        self, token: str, current_time: Optional[datetime] = None
    ):
        return await self.token_handler.blacklist_token(token, current_time)

    async def is_token_blacklisted(self, token: str) -> bool:
        return await self.token_handler.is_token_blacklisted(token)

    async def clean_expired_blacklisted_tokens(
        self,
        max_age_hours: int = 7 * 24,
        current_time: Optional[datetime] = None,
    ):
        return await self.token_handler.clean_expired_blacklisted_tokens(
            max_age_hours, current_time
        )

    # User handler methods
    async def get_user_by_id(self, user_id: UUID) -> UserResponse:
        return await self.user_handler.get_user_by_id(user_id)

    async def get_user_by_email(self, email: str) -> UserResponse:
        return await self.user_handler.get_user_by_email(email)

    async def create_user(self, email: str, password: str) -> UserResponse:
        return await self.user_handler.create_user(email, password)

    async def update_user(self, user: UserResponse) -> UserResponse:
        return await self.user_handler.update_user(user)

    async def delete_user_relational(self, user_id: UUID) -> None:
        return await self.user_handler.delete_user_relational(user_id)

    async def update_user_password(
        self, user_id: UUID, new_hashed_password: str
    ):
        return await self.user_handler.update_user_password(
            user_id, new_hashed_password
        )

    async def get_all_users(self) -> list[UserResponse]:
        return await self.user_handler.get_all_users()

    async def store_verification_code(
        self, user_id: UUID, verification_code: str, expiry: datetime
    ):
        return await self.user_handler.store_verification_code(
            user_id, verification_code, expiry
        )

    async def verify_user(self, verification_code: str) -> None:
        return await self.user_handler.verify_user(verification_code)

    async def remove_verification_code(self, verification_code: str):
        return await self.user_handler.remove_verification_code(
            verification_code
        )

    async def expire_verification_code(self, user_id: UUID):
        return await self.user_handler.expire_verification_code(user_id)

    async def store_reset_token(
        self, user_id: UUID, reset_token: str, expiry: datetime
    ):
        return await self.user_handler.store_reset_token(
            user_id, reset_token, expiry
        )

    async def get_user_id_by_reset_token(
        self, reset_token: str
    ) -> Optional[UUID]:
        return await self.user_handler.get_user_id_by_reset_token(reset_token)

    async def remove_reset_token(self, user_id: UUID):
        return await self.user_handler.remove_reset_token(user_id)

    async def remove_user_from_all_collections(self, user_id: UUID):
        return await self.user_handler.remove_user_from_all_collections(
            user_id
        )

    async def add_user_to_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> None:
        return await self.user_handler.add_user_to_collection(
            user_id, collection_id
        )

    async def remove_user_from_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> None:
        return await self.user_handler.remove_user_from_collection(
            user_id, collection_id
        )

    async def get_users_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[UserResponse], int]]:
        return await self.user_handler.get_users_in_collection(
            collection_id, offset, limit
        )

    async def mark_user_as_superuser(self, user_id: UUID):
        return await self.user_handler.mark_user_as_superuser(user_id)

    async def get_user_id_by_verification_code(
        self, verification_code: str
    ) -> Optional[UUID]:
        return await self.user_handler.get_user_id_by_verification_code(
            verification_code
        )

    async def mark_user_as_verified(self, user_id: UUID):
        return await self.user_handler.mark_user_as_verified(user_id)

    async def get_users_overview(
        self,
        user_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = -1,
    ) -> dict[str, Union[list[UserStats], int]]:
        return await self.user_handler.get_users_overview(
            user_ids, offset, limit
        )

    # Vector handler methods
    async def upsert(self, entry: VectorEntry) -> None:
        return await self.vector_handler.upsert(entry)

    async def upsert_entries(self, entries: list[VectorEntry]) -> None:
        return await self.vector_handler.upsert_entries(entries)

    async def semantic_search(
        self, query_vector: list[float], search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        return await self.vector_handler.semantic_search(
            query_vector, search_settings
        )

    async def full_text_search(
        self, query_text: str, search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        return await self.vector_handler.full_text_search(
            query_text, search_settings
        )

    async def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        search_settings: VectorSearchSettings,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        return await self.vector_handler.hybrid_search(
            query_text, query_vector, search_settings, *args, **kwargs
        )

    async def delete(
        self, filters: dict[str, Any]
    ) -> dict[str, dict[str, str]]:
        return await self.vector_handler.delete(filters)

    async def assign_document_to_collection_vector(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        return await self.vector_handler.assign_document_to_collection_vector(
            document_id, collection_id
        )

    async def remove_document_from_collection_vector(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        return (
            await self.vector_handler.remove_document_from_collection_vector(
                document_id, collection_id
            )
        )

    async def delete_user_vector(self, user_id: UUID) -> None:
        return await self.vector_handler.delete_user_vector(user_id)

    async def delete_collection_vector(self, collection_id: UUID) -> None:
        return await self.vector_handler.delete_collection_vector(
            collection_id
        )

    async def get_document_chunks(
        self,
        document_id: UUID,
        offset: int = 0,
        limit: int = -1,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        return await self.vector_handler.get_document_chunks(
            document_id, offset, limit, include_vectors
        )

    async def create_index(
        self,
        table_name: Optional[VectorTableName] = None,
        index_measure: IndexMeasure = IndexMeasure.cosine_distance,
        index_method: IndexMethod = IndexMethod.auto,
        index_arguments: Optional[
            Union[IndexArgsIVFFlat, IndexArgsHNSW]
        ] = None,
        index_name: Optional[str] = None,
        concurrently: bool = True,
    ) -> None:
        return await self.vector_handler.create_index(
            table_name,
            index_measure,
            index_method,
            index_arguments,
            index_name,
            concurrently,
        )

    async def list_indices(
        self, table_name: Optional[VectorTableName] = None
    ) -> list[dict]:
        return await self.vector_handler.list_indices(table_name)

    async def delete_index(
        self,
        index_name: str,
        table_name: Optional[VectorTableName] = None,
        concurrently: bool = True,
    ) -> None:
        return await self.vector_handler.delete_index(
            index_name, table_name, concurrently
        )

    async def select_index(
        self, index_name: str, table_name: Optional[VectorTableName] = None
    ) -> None:
        return await self.vector_handler.select_index(index_name, table_name)

    async def get_semantic_neighbors(
        self,
        document_id: UUID,
        chunk_id: UUID,
        limit: int = 10,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        return await self.vector_handler.get_semantic_neighbors(
            document_id, chunk_id, limit, similarity_threshold
        )
