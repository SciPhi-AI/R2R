import logging
from abc import ABC, abstractmethod
from datetime import datetime
from io import BytesIO
from typing import Any, BinaryIO, Optional, Sequence, Tuple
from uuid import UUID

from pydantic import BaseModel

from core.base.abstractions import (
    ChunkSearchResult,
    Community,
    DocumentResponse,
    Entity,
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEntityDeduplicationSettings,
    Message,
    Relationship,
    SearchSettings,
    User,
    VectorEntry,
    VectorTableName,
)
from core.base.api.models import CollectionResponse, GraphResponse

from ..logger import RunInfoLog
from ..logger.base import RunType
from .base import Provider, ProviderConfig

"""Base classes for knowledge graph providers."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple
from uuid import UUID

from ..abstractions import (
    Community,
    Entity,
    GraphSearchSettings,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEntityDeduplicationSettings,
    KGExtraction,
    Relationship,
)
from .base import ProviderConfig

logger = logging.getLogger()


class PostgresConfigurationSettings(BaseModel):
    """
    Configuration settings with defaults defined by the PGVector docker image.

    These settings are helpful in managing the connections to the database.
    To tune these settings for a specific deployment, see https://pgtune.leopard.in.ua/
    """

    checkpoint_completion_target: Optional[float] = 0.9
    default_statistics_target: Optional[int] = 100
    effective_io_concurrency: Optional[int] = 1
    effective_cache_size: Optional[int] = 524288
    huge_pages: Optional[str] = "try"
    maintenance_work_mem: Optional[int] = 65536
    max_connections: Optional[int] = 256
    max_parallel_workers_per_gather: Optional[int] = 2
    max_parallel_workers: Optional[int] = 8
    max_parallel_maintenance_workers: Optional[int] = 2
    max_wal_size: Optional[int] = 1024
    max_worker_processes: Optional[int] = 8
    min_wal_size: Optional[int] = 80
    shared_buffers: Optional[int] = 16384
    statement_cache_size: Optional[int] = 100
    random_page_cost: Optional[float] = 4
    wal_buffers: Optional[int] = 512
    work_mem: Optional[int] = 4096


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

    # KG settings
    batch_size: Optional[int] = 1
    kg_store_path: Optional[str] = None
    graph_enrichment_settings: KGEnrichmentSettings = KGEnrichmentSettings()
    graph_creation_settings: KGCreationSettings = KGCreationSettings()
    graph_entity_deduplication_settings: KGEntityDeduplicationSettings = (
        KGEntityDeduplicationSettings()
    )
    graph_search_settings: GraphSearchSettings = GraphSearchSettings()

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
        params: Optional[dict[str, Any] | Sequence[Any]] = None,
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
        params: Optional[dict[str, Any] | Sequence[Any]] = None,
    ):
        pass

    @abstractmethod
    def fetchrow_query(
        self,
        query: str,
        params: Optional[dict[str, Any] | Sequence[Any]] = None,
    ):
        pass

    @abstractmethod
    async def initialize(self, pool: Any):
        pass


class Handler(ABC):
    def __init__(
        self,
        project_name: str,
        connection_manager: DatabaseConnectionManager,
    ):
        self.project_name = project_name
        self.connection_manager = connection_manager

    def _get_table_name(self, base_name: str) -> str:
        return f"{self.project_name}.{base_name}"

    @abstractmethod
    def create_tables(self):
        pass


class DocumentHandler(Handler):

    @abstractmethod
    async def upsert_documents_overview(
        self,
        documents_overview: DocumentResponse | list[DocumentResponse],
    ) -> None:
        pass

    @abstractmethod
    async def delete_from_documents_overview(
        self,
        document_id: UUID,
        version: Optional[str] = None,
    ) -> None:
        pass

    @abstractmethod
    async def get_documents_overview(
        self,
        offset: int,
        limit: int,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def get_workflow_status(
        self,
        id: UUID | list[UUID],
        status_type: str,
    ):
        pass

    @abstractmethod
    async def set_workflow_status(
        self,
        id: UUID | list[UUID],
        status_type: str,
        status: str,
    ):
        pass

    @abstractmethod
    async def get_document_ids_by_status(
        self,
        status_type: str,
        status: str | list[str],
        collection_id: Optional[UUID] = None,
    ):
        pass

    @abstractmethod
    async def search_documents(
        self,
        query_text: str,
        query_embedding: Optional[list[float]] = None,
        search_settings: Optional[SearchSettings] = None,
    ) -> list[DocumentResponse]:
        pass


class CollectionsHandler(Handler):
    @abstractmethod
    async def collection_exists(self, collection_id: UUID) -> bool:
        pass

    @abstractmethod
    async def create_collection(
        self,
        owner_id: UUID,
        name: Optional[str] = None,
        description: str = "",
        collection_id: Optional[UUID] = None,
    ) -> CollectionResponse:
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
    async def documents_in_collection(
        self, collection_id: UUID, offset: int, limit: int
    ) -> dict[str, list[DocumentResponse] | int]:
        pass

    @abstractmethod
    async def get_collections_overview(
        self,
        offset: int,
        limit: int,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[CollectionResponse] | int]:
        pass

    @abstractmethod
    async def assign_document_to_collection_relational(
        self,
        document_id: UUID,
        collection_id: UUID,
    ) -> UUID:
        pass

    @abstractmethod
    async def remove_document_from_collection_relational(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        pass


class TokenHandler(Handler):

    @abstractmethod
    async def create_tables(self):
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
    async def get_user_by_id(self, user_id: UUID) -> User:
        pass

    @abstractmethod
    async def get_user_by_email(self, email: str) -> User:
        pass

    @abstractmethod
    async def create_user(
        self, email: str, password: str, is_superuser: bool
    ) -> User:
        pass

    @abstractmethod
    async def update_user(self, user: User) -> User:
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
    async def get_all_users(self) -> list[User]:
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
    ) -> bool:
        pass

    @abstractmethod
    async def remove_user_from_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> bool:
        pass

    @abstractmethod
    async def get_users_in_collection(
        self, collection_id: UUID, offset: int, limit: int
    ) -> dict[str, list[User] | int]:
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
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[User] | int]:
        pass

    @abstractmethod
    async def get_user_validation_data(
        self,
        user_id: UUID,
    ) -> dict:
        """
        Get verification data for a specific user.
        This method should be called after superuser authorization has been verified.
        """
        pass


class ChunkHandler(Handler):
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
        self, query_vector: list[float], search_settings: SearchSettings
    ) -> list[ChunkSearchResult]:
        pass

    @abstractmethod
    async def full_text_search(
        self, query_text: str, search_settings: SearchSettings
    ) -> list[ChunkSearchResult]:
        pass

    @abstractmethod
    async def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        search_settings: SearchSettings,
        *args,
        **kwargs,
    ) -> list[ChunkSearchResult]:
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
    async def list_document_chunks(
        self,
        document_id: UUID,
        offset: int,
        limit: int,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def get_chunk(self, chunk_id: UUID) -> dict:
        pass

    @abstractmethod
    async def create_index(
        self,
        table_name: Optional[VectorTableName] = None,
        index_measure: IndexMeasure = IndexMeasure.cosine_distance,
        index_method: IndexMethod = IndexMethod.auto,
        index_arguments: Optional[IndexArgsIVFFlat | IndexArgsHNSW] = None,
        index_name: Optional[str] = None,
        index_column: Optional[str] = None,
        concurrently: bool = True,
    ) -> None:
        pass

    @abstractmethod
    async def list_indices(
        self, offset: int, limit: int, filters: Optional[dict] = None
    ) -> dict:
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
    async def get_semantic_neighbors(
        self,
        offset: int,
        limit: int,
        document_id: UUID,
        chunk_id: UUID,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def list_chunks(
        self,
        offset: int,
        limit: int,
        filters: Optional[dict[str, Any]] = None,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        pass


class EntityHandler(Handler):

    @abstractmethod
    async def create(self, *args: Any, **kwargs: Any) -> Entity:
        """Create entities in storage."""
        pass

    @abstractmethod
    async def get(self, *args: Any, **kwargs: Any) -> list[Entity]:
        """Get entities from storage."""
        pass

    @abstractmethod
    async def update(self, *args: Any, **kwargs: Any) -> Entity:
        """Update entities in storage."""
        pass

    @abstractmethod
    async def delete(self, *args: Any, **kwargs: Any) -> None:
        """Delete entities from storage."""
        pass


class RelationshipHandler(Handler):
    @abstractmethod
    async def create(self, *args: Any, **kwargs: Any) -> Relationship:
        """Add relationships to storage."""
        pass

    @abstractmethod
    async def get(self, *args: Any, **kwargs: Any) -> list[Relationship]:
        """Get relationships from storage."""
        pass

    @abstractmethod
    async def update(self, *args: Any, **kwargs: Any) -> Relationship:
        """Update relationships in storage."""
        pass

    @abstractmethod
    async def delete(self, *args: Any, **kwargs: Any) -> None:
        """Delete relationships from storage."""
        pass


class CommunityHandler(Handler):
    @abstractmethod
    async def create(self, *args: Any, **kwargs: Any) -> Community:
        """Create communities in storage."""
        pass

    @abstractmethod
    async def get(self, *args: Any, **kwargs: Any) -> list[Community]:
        """Get communities from storage."""
        pass

    @abstractmethod
    async def update(self, *args: Any, **kwargs: Any) -> Community:
        """Update communities in storage."""
        pass

    @abstractmethod
    async def delete(self, *args: Any, **kwargs: Any) -> None:
        """Delete communities from storage."""
        pass


class GraphHandler(Handler):

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @abstractmethod
    async def create(self, *args: Any, **kwargs: Any) -> GraphResponse:
        """Create graph"""
        pass

    @abstractmethod
    async def update(
        self,
        graph_id: UUID,
        name: Optional[str],
        description: Optional[str],
    ) -> GraphResponse:
        """Update graph"""
        pass


class PromptHandler(Handler):
    """Abstract base class for prompt handling operations."""

    @abstractmethod
    async def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> None:
        """Add a new prompt template to the database."""
        pass

    @abstractmethod
    async def get_cached_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> str:
        """Retrieve and format a prompt template."""
        pass

    @abstractmethod
    async def get_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> str:
        """Retrieve and format a prompt template."""
        pass

    @abstractmethod
    async def get_all_prompts(self) -> dict[str, Any]:
        """Retrieve all stored prompts."""
        pass

    @abstractmethod
    async def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        """Update an existing prompt template."""
        pass

    @abstractmethod
    async def delete_prompt(self, name: str) -> None:
        """Delete a prompt template."""
        pass

    @abstractmethod
    async def get_message_payload(
        self,
        system_prompt_name: Optional[str] = None,
        system_role: str = "system",
        system_inputs: dict = {},
        system_prompt_override: Optional[str] = None,
        task_prompt_name: Optional[str] = None,
        task_role: str = "user",
        task_inputs: dict = {},
        task_prompt_override: Optional[str] = None,
    ) -> list[dict]:
        """Get the payload of a prompt."""
        pass


class FileHandler(Handler):
    """Abstract base class for file handling operations."""

    @abstractmethod
    async def upsert_file(
        self,
        document_id: UUID,
        file_name: str,
        file_oid: int,
        file_size: int,
        file_type: Optional[str] = None,
    ) -> None:
        """Add or update a file entry in storage."""
        pass

    @abstractmethod
    async def store_file(
        self,
        document_id: UUID,
        file_name: str,
        file_content: BytesIO,
        file_type: Optional[str] = None,
    ) -> None:
        """Store a new file in the database."""
        pass

    @abstractmethod
    async def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        """Retrieve a file from storage."""
        pass

    @abstractmethod
    async def delete_file(self, document_id: UUID) -> bool:
        """Delete a file from storage."""
        pass

    @abstractmethod
    async def get_files_overview(
        self,
        offset: int,
        limit: int,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
    ) -> list[dict]:
        """Get an overview of stored files."""
        pass


class LoggingHandler(Handler):
    """Abstract base class defining the interface for logging handlers."""

    @abstractmethod
    async def close(self) -> None:
        """Close any open connections."""
        pass

    # Basic logging methods
    @abstractmethod
    async def log(self, run_id: UUID, key: str, value: str) -> None:
        """Log a key-value pair for a specific run."""
        pass

    @abstractmethod
    async def info_log(
        self, run_id: UUID, run_type: RunType, user_id: UUID
    ) -> None:
        """Log run information."""
        pass

    @abstractmethod
    async def get_logs(
        self, run_ids: list[UUID], limit_per_run: int = 10
    ) -> list[dict]:
        """Retrieve logs for specified run IDs."""
        pass

    @abstractmethod
    async def get_info_logs(
        self,
        offset: int,
        limit: int,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        """Retrieve run information logs with filtering options."""
        pass

    # Conversation management methods
    @abstractmethod
    async def create_conversation(self) -> dict:
        """Create a new conversation and return its ID."""
        pass

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all associated data."""
        pass

    @abstractmethod
    async def get_conversations(
        self,
        offset: int,
        limit: int,
        conversation_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[dict] | int]:
        """Get an overview of conversations with pagination."""
        pass

    # Message management methods
    @abstractmethod
    async def add_message(
        self,
        conversation_id: str,
        content: Message,
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Add a message to a conversation."""
        pass

    @abstractmethod
    async def edit_message(
        self, message_id: str, new_content: str
    ) -> Tuple[str, str]:
        """Edit an existing message and return new message ID and branch ID."""
        pass

    @abstractmethod
    async def get_conversation(
        self, conversation_id: str, branch_id: Optional[str] = None
    ) -> list[Tuple[str, Message]]:
        """Retrieve all messages in a conversation branch."""
        pass

    # Branch management methods
    @abstractmethod
    async def get_branches(self, conversation_id: str) -> list[dict]:
        """Get an overview of all branches in a conversation."""
        pass

    @abstractmethod
    async def get_next_branch(self, current_branch_id: str) -> Optional[str]:
        """Get the ID of the next branch in chronological order."""
        pass

    @abstractmethod
    async def get_prev_branch(self, current_branch_id: str) -> Optional[str]:
        """Get the ID of the previous branch in chronological order."""
        pass

    @abstractmethod
    async def branch_at_message(self, message_id: str) -> str:
        """Create a new branch starting at a specific message."""
        pass


class DatabaseProvider(Provider):
    connection_manager: DatabaseConnectionManager
    document_handler: DocumentHandler
    collections_handler: CollectionsHandler
    token_handler: TokenHandler
    user_handler: UserHandler
    vector_handler: ChunkHandler
    entity_handler: EntityHandler
    relationship_handler: RelationshipHandler
    graph_handler: GraphHandler
    prompt_handler: PromptHandler
    file_handler: FileHandler
    logging_handler: LoggingHandler
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
        self,
        documents_overview: DocumentResponse | list[DocumentResponse],
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
        offset: int,
        limit: int,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
    ) -> dict[str, Any]:
        return await self.document_handler.get_documents_overview(
            offset=offset,
            limit=limit,
            filter_user_ids=filter_user_ids,
            filter_document_ids=filter_document_ids,
            filter_collection_ids=filter_collection_ids,
        )

    async def get_workflow_status(
        self, id: UUID | list[UUID], status_type: str
    ):
        return await self.document_handler.get_workflow_status(id, status_type)

    async def set_workflow_status(
        self,
        id: UUID | list[UUID],
        status_type: str,
        status: str,
    ):
        return await self.document_handler.set_workflow_status(
            id, status_type, status
        )

    async def get_document_ids_by_status(
        self,
        status_type: str,
        status: str | list[str],
        collection_id: Optional[UUID] = None,
    ):
        return await self.document_handler.get_document_ids_by_status(
            status_type, status, collection_id
        )

    # Collection handler methods
    async def collection_exists(self, collection_id: UUID) -> bool:
        return await self.collections_handler.collection_exists(collection_id)

    async def create_collection(
        self,
        owner_id: UUID,
        name: Optional[str] = None,
        description: str = "",
        collection_id: Optional[UUID] = None,
    ) -> CollectionResponse:
        return await self.collections_handler.create_collection(
            owner_id=owner_id,
            name=name,
            description=description,
            collection_id=collection_id,
        )

    async def update_collection(
        self,
        collection_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> CollectionResponse:
        return await self.collections_handler.update_collection(
            collection_id, name, description
        )

    async def delete_collection_relational(self, collection_id: UUID) -> None:
        return await self.collections_handler.delete_collection_relational(
            collection_id
        )

    async def documents_in_collection(
        self, collection_id: UUID, offset: int, limit: int
    ) -> dict[str, list[DocumentResponse] | int]:
        return await self.collections_handler.documents_in_collection(
            collection_id, offset, limit
        )

    async def get_collections_overview(
        self,
        offset: int,
        limit: int,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[CollectionResponse] | int]:
        return await self.collections_handler.get_collections_overview(
            offset=offset,
            limit=limit,
            filter_user_ids=filter_user_ids,
            filter_document_ids=filter_document_ids,
            filter_collection_ids=filter_collection_ids,
        )

    async def assign_document_to_collection_relational(
        self,
        document_id: UUID,
        collection_id: UUID,
    ) -> UUID:
        return await self.collections_handler.assign_document_to_collection_relational(
            document_id=document_id,
            collection_id=collection_id,
        )

    async def remove_document_from_collection_relational(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        return await self.collections_handler.remove_document_from_collection_relational(
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
    async def get_user_by_id(self, user_id: UUID) -> User:
        return await self.user_handler.get_user_by_id(user_id)

    async def get_user_by_email(self, email: str) -> User:
        return await self.user_handler.get_user_by_email(email)

    async def create_user(
        self, email: str, password: str, is_superuser: bool = False
    ) -> User:
        return await self.user_handler.create_user(
            email=email,
            password=password,
            is_superuser=is_superuser,
        )

    async def update_user(self, user: User) -> User:
        return await self.user_handler.update_user(user)

    async def delete_user_relational(self, user_id: UUID) -> None:
        return await self.user_handler.delete_user_relational(user_id)

    async def update_user_password(
        self, user_id: UUID, new_hashed_password: str
    ):
        return await self.user_handler.update_user_password(
            user_id, new_hashed_password
        )

    async def get_all_users(self) -> list[User]:
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
    ) -> bool:
        return await self.user_handler.add_user_to_collection(
            user_id, collection_id
        )

    async def remove_user_from_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> bool:
        return await self.user_handler.remove_user_from_collection(
            user_id, collection_id
        )

    async def get_users_in_collection(
        self, collection_id: UUID, offset: int, limit: int
    ) -> dict[str, list[User] | int]:
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
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[User] | int]:
        return await self.user_handler.get_users_overview(
            offset=offset,
            limit=limit,
            user_ids=user_ids,
        )

    async def get_user_validation_data(
        self,
        user_id: UUID,
    ) -> dict:
        return await self.user_handler.get_user_validation_data(
            user_id=user_id
        )

    # Vector handler methods
    async def upsert(self, entry: VectorEntry) -> None:
        return await self.vector_handler.upsert(entry)

    async def upsert_entries(self, entries: list[VectorEntry]) -> None:
        return await self.vector_handler.upsert_entries(entries)

    async def semantic_search(
        self, query_vector: list[float], search_settings: SearchSettings
    ) -> list[ChunkSearchResult]:
        return await self.vector_handler.semantic_search(
            query_vector, search_settings
        )

    async def full_text_search(
        self, query_text: str, search_settings: SearchSettings
    ) -> list[ChunkSearchResult]:
        return await self.vector_handler.full_text_search(
            query_text, search_settings
        )

    async def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        search_settings: SearchSettings,
        *args,
        **kwargs,
    ) -> list[ChunkSearchResult]:
        return await self.vector_handler.hybrid_search(
            query_text, query_vector, search_settings, *args, **kwargs
        )

    async def search_documents(
        self,
        query_text: str,
        settings: SearchSettings,
        query_embedding: Optional[list[float]] = None,
    ) -> list[DocumentResponse]:
        return await self.document_handler.search_documents(
            query_text, query_embedding, settings
        )

    async def delete(
        self, filters: dict[str, Any]
    ) -> dict[str, dict[str, str]]:
        result = await self.vector_handler.delete(filters)
        try:
            await self.entity_handler.delete(parent_id=filters["id"]["$eq"])
        except Exception as e:
            logger.debug(f"Attempt to delete entity failed: {e}")
        try:
            await self.relationship_handler.delete(
                parent_id=filters["id"]["$eq"]
            )
        except Exception as e:
            logger.debug(f"Attempt to delete relationship failed: {e}")
        return result

    async def assign_document_to_collection_vector(
        self,
        document_id: UUID,
        collection_id: UUID,
    ) -> None:
        return await self.vector_handler.assign_document_to_collection_vector(
            document_id=document_id,
            collection_id=collection_id,
        )

    async def remove_document_from_collection_vector(
        self,
        document_id: UUID,
        collection_id: UUID,
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

    async def list_document_chunks(
        self,
        document_id: UUID,
        offset: int,
        limit: int,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        return await self.vector_handler.list_document_chunks(
            document_id=document_id,
            offset=offset,
            limit=limit,
            include_vectors=include_vectors,
        )

    async def get_chunk(self, chunk_id: UUID) -> dict:
        return await self.vector_handler.get_chunk(chunk_id)

    async def create_index(
        self,
        table_name: Optional[VectorTableName] = None,
        index_measure: IndexMeasure = IndexMeasure.cosine_distance,
        index_method: IndexMethod = IndexMethod.auto,
        index_arguments: Optional[IndexArgsIVFFlat | IndexArgsHNSW] = None,
        index_name: Optional[str] = None,
        index_column: Optional[str] = None,
        concurrently: bool = True,
    ) -> None:
        return await self.vector_handler.create_index(
            table_name,
            index_measure,
            index_method,
            index_arguments,
            index_name,
            index_column,
            concurrently,
        )

    async def list_indices(
        self, offset: int, limit: int, filters: Optional[dict] = None
    ) -> dict:
        return await self.vector_handler.list_indices(offset, limit, filters)

    async def delete_index(
        self,
        index_name: str,
        table_name: Optional[VectorTableName] = None,
        concurrently: bool = True,
    ) -> None:
        return await self.vector_handler.delete_index(
            index_name, table_name, concurrently
        )

    async def get_semantic_neighbors(
        self,
        document_id: UUID,
        chunk_id: UUID,
        offset: int,
        limit: int,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        return await self.vector_handler.get_semantic_neighbors(
            offset=offset,
            limit=limit,
            document_id=document_id,
            chunk_id=chunk_id,
            similarity_threshold=similarity_threshold,
        )

    async def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> None:
        return await self.prompt_handler.add_prompt(
            name, template, input_types
        )

    async def get_cached_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> str:
        return await self.prompt_handler.get_cached_prompt(
            prompt_name, inputs, prompt_override
        )

    async def get_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> str:
        return await self.prompt_handler.get_prompt(
            prompt_name, inputs, prompt_override
        )

    async def get_all_prompts(self) -> dict[str, Any]:
        return await self.prompt_handler.get_all_prompts()

    async def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        return await self.prompt_handler.update_prompt(
            name, template, input_types
        )

    async def delete_prompt(self, name: str) -> None:
        return await self.prompt_handler.delete_prompt(name)

    async def upsert_file(
        self,
        document_id: UUID,
        file_name: str,
        file_oid: int,
        file_size: int,
        file_type: Optional[str] = None,
    ) -> None:
        return await self.file_handler.upsert_file(
            document_id, file_name, file_oid, file_size, file_type
        )

    async def store_file(
        self,
        document_id: UUID,
        file_name: str,
        file_content: BytesIO,
        file_type: Optional[str] = None,
    ) -> None:
        return await self.file_handler.store_file(
            document_id, file_name, file_content, file_type
        )

    async def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        return await self.file_handler.retrieve_file(document_id)

    async def delete_file(self, document_id: UUID) -> bool:
        return await self.file_handler.delete_file(document_id)

    async def get_files_overview(
        self,
        offset: int,
        limit: int,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
    ) -> list[dict]:
        return await self.file_handler.get_files_overview(
            offset=offset,
            limit=limit,
            filter_document_ids=filter_document_ids,
            filter_file_names=filter_file_names,
        )

    async def log(
        self,
        run_id: UUID,
        key: str,
        value: str,
    ) -> None:
        """Add a new log entry."""
        return await self.logging_handler.log(run_id, key, value)

    async def info_log(
        self,
        run_id: UUID,
        run_type: RunType,
        user_id: UUID,
    ) -> None:
        """Add or update a log info entry."""
        return await self.logging_handler.info_log(run_id, run_type, user_id)

    async def get_info_logs(
        self,
        offset: int,
        limit: int,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        """Retrieve log info entries with filtering and pagination."""
        return await self.logging_handler.get_info_logs(
            offset, limit, run_type_filter, user_ids
        )

    async def get_logs(
        self,
        run_ids: list[UUID],
        limit_per_run: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve logs for specified run IDs with a per-run limit."""
        return await self.logging_handler.get_logs(run_ids, limit_per_run)

    async def create_conversation(self) -> dict:
        """Create a new conversation and return its ID and timestamp."""
        return await self.logging_handler.create_conversation()

    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all associated data."""
        return await self.logging_handler.delete_conversation(conversation_id)

    async def get_conversations(
        self,
        offset: int,
        limit: int,
        conversation_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[dict] | int]:
        """Get an overview of conversations with pagination."""
        return await self.logging_handler.get_conversations(
            offset=offset,
            limit=limit,
            conversation_ids=conversation_ids,
        )

    async def add_message(
        self,
        conversation_id: str,
        content: Message,
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Add a message to a conversation."""
        return await self.logging_handler.add_message(
            conversation_id, content, parent_id, metadata
        )

    async def edit_message(
        self, message_id: str, new_content: str
    ) -> Tuple[str, str]:
        """Edit an existing message and return new message ID and branch ID."""
        return await self.logging_handler.edit_message(message_id, new_content)

    async def get_conversation(
        self, conversation_id: str, branch_id: Optional[str] = None
    ) -> list[Tuple[str, Message]]:
        """Retrieve all messages in a conversation branch."""
        return await self.logging_handler.get_conversation(
            conversation_id, branch_id
        )

    async def get_branches(self, conversation_id: str) -> list[dict]:
        """Get an overview of all branches in a conversation."""
        return await self.logging_handler.get_branches(conversation_id)

    async def get_next_branch(self, current_branch_id: str) -> Optional[str]:
        """Get the ID of the next branch in chronological order."""
        return await self.logging_handler.get_next_branch(current_branch_id)

    async def get_prev_branch(self, current_branch_id: str) -> Optional[str]:
        """Get the ID of the previous branch in chronological order."""
        return await self.logging_handler.get_prev_branch(current_branch_id)

    async def branch_at_message(self, message_id: str) -> str:
        """Create a new branch starting at a specific message."""
        return await self.logging_handler.branch_at_message(message_id)

    async def list_chunks(
        self,
        offset: int,
        limit: int,
        filters: Optional[dict[str, Any]] = None,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        return await self.vector_handler.list_chunks(
            offset, limit, filters, include_vectors
        )
