import logging
from abc import ABC, abstractmethod
from datetime import datetime
from io import BytesIO
from typing import (
    Any,
    AsyncGenerator,
    BinaryIO,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from uuid import UUID

from pydantic import BaseModel

from core.base import (
    CommunityReport,
    Entity,
    KGExtraction,
    Message,
    Triple,
    VectorEntry,
)
from core.base.abstractions import (
    DocumentInfo,
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEntityDeduplicationSettings,
    UserStats,
    VectorEntry,
    VectorQuantizationType,
    VectorSearchResult,
    VectorSearchSettings,
    VectorTableName,
)
from core.base.api.models import (
    CollectionOverviewResponse,
    CollectionResponse,
    KGCreationEstimationResponse,
    KGDeduplicationEstimationResponse,
    KGEnrichmentEstimationResponse,
    UserResponse,
)
from core.base.utils import _decorate_vector_type

from ..logger import RunInfoLog
from ..logger.base import RunType
from .base import Provider, ProviderConfig

"""Base classes for knowledge graph providers."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple
from uuid import UUID

from ..abstractions import (
    CommunityReport,
    Entity,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEntityDeduplicationSettings,
    KGExtraction,
    KGSearchSettings,
    RelationshipType,
    Triple,
)
from .base import ProviderConfig

logger = logging.getLogger()


def escape_braces(s: str) -> str:
    """
    Escape braces in a string.
    This is a placeholder function - implement the actual logic as needed.
    """
    # Implement your escape_braces logic here
    return s.replace("{", "{{").replace("}", "}}")


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

    # KG settings
    batch_size: Optional[int] = 1
    kg_store_path: Optional[str] = None
    kg_enrichment_settings: KGEnrichmentSettings = KGEnrichmentSettings()
    kg_creation_settings: KGCreationSettings = KGCreationSettings()
    kg_entity_deduplication_settings: KGEntityDeduplicationSettings = (
        KGEntityDeduplicationSettings()
    )
    kg_search_settings: KGSearchSettings = KGSearchSettings()

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
    def create_tables(self):
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
    async def get_chunk(self, extraction_id: UUID) -> Optional[dict[str, Any]]:
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
    async def get_semantic_neighbors(
        self,
        document_id: UUID,
        chunk_id: UUID,
        limit: int = 10,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        pass


class KGHandler(Handler):
    """Base handler for Knowledge Graph operations."""

    @abstractmethod
    async def create_tables(self) -> None:
        """Create required database tables."""
        pass

    @abstractmethod
    async def add_kg_extractions(
        self,
        kg_extractions: list[KGExtraction],
        table_prefix: str = "chunk_",
    ) -> Tuple[int, int]:
        """Add KG extractions to storage."""
        pass

    @abstractmethod
    async def add_entities(
        self,
        entities: list[Entity],
        table_name: str,
        conflict_columns: list[str] = [],
    ) -> Any:
        """Add entities to storage."""
        pass

    @abstractmethod
    async def add_triples(
        self,
        triples: list[Triple],
        table_name: str = "chunk_triple",
    ) -> None:
        """Add triples to storage."""
        pass

    @abstractmethod
    async def get_entity_map(
        self, offset: int, limit: int, document_id: UUID
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Get entity map for a document."""
        pass

    @abstractmethod
    async def upsert_embeddings(
        self,
        data: List[Tuple[Any]],
        table_name: str,
    ) -> None:
        """Upsert embeddings into storage."""
        pass

    @abstractmethod
    async def vector_query(
        self, query: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        """Perform vector similarity search."""
        pass

    # Community management
    @abstractmethod
    async def add_communities(self, communities: List[Any]) -> None:
        """Add communities to storage."""
        pass

    @abstractmethod
    async def get_communities(
        self,
        collection_id: UUID,
        offset: int = 0,
        limit: int = 100,
        levels: Optional[list[int]] = None,
        community_numbers: Optional[list[int]] = None,
    ) -> dict:
        """Get communities for a collection."""
        pass

    @abstractmethod
    async def get_community_count(self, collection_id: UUID) -> int:
        """Get total number of communities for a collection."""
        pass

    @abstractmethod
    async def add_community_report(
        self, community_report: CommunityReport
    ) -> None:
        """Add a community report."""
        pass

    @abstractmethod
    async def get_community_details(
        self, community_number: int, collection_id: UUID
    ) -> Tuple[int, list[Entity], list[Triple]]:
        """Get detailed information about a community."""
        pass

    @abstractmethod
    async def get_community_reports(
        self, collection_id: UUID
    ) -> List[CommunityReport]:
        """Get community reports for a collection."""
        pass

    @abstractmethod
    async def check_community_reports_exist(
        self, collection_id: UUID, offset: int, limit: int
    ) -> List[int]:
        """Check which community reports exist."""
        pass

    @abstractmethod
    async def perform_graph_clustering(
        self,
        collection_id: UUID,
        leiden_params: Dict[str, Any],
    ) -> int:
        """Perform graph clustering."""
        pass

    # Graph operations
    @abstractmethod
    async def delete_graph_for_collection(
        self, collection_id: UUID, cascade: bool = False
    ) -> None:
        """Delete graph data for a collection."""
        pass

    @abstractmethod
    async def delete_node_via_document_id(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        """Delete a node using document ID."""
        pass

    # Entity and Triple management
    @abstractmethod
    async def get_entities(
        self,
        collection_id: UUID,
        offset: int = 0,
        limit: int = -1,
        entity_ids: Optional[List[str]] = None,
        entity_names: Optional[List[str]] = None,
        entity_table_name: str = "document_entity",
    ) -> dict:
        """Get entities from storage."""
        pass

    @abstractmethod
    async def get_triples(
        self,
        collection_id: UUID,
        offset: int = 0,
        limit: int = 100,
        entity_names: Optional[List[str]] = None,
        triple_ids: Optional[List[str]] = None,
    ) -> dict:
        """Get triples from storage."""
        pass

    @abstractmethod
    async def get_entity_count(
        self,
        collection_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
        distinct: bool = False,
        entity_table_name: str = "document_entity",
    ) -> int:
        """Get entity count."""
        pass

    @abstractmethod
    async def get_triple_count(
        self,
        collection_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
    ) -> int:
        """Get triple count."""
        pass

    # Cost estimation methods
    @abstractmethod
    async def get_creation_estimate(
        self, collection_id: UUID, kg_creation_settings: KGCreationSettings
    ) -> KGCreationEstimationResponse:
        """Get creation cost estimate."""
        pass

    @abstractmethod
    async def get_enrichment_estimate(
        self, collection_id: UUID, kg_enrichment_settings: KGEnrichmentSettings
    ) -> KGEnrichmentEstimationResponse:
        """Get enrichment cost estimate."""
        pass

    @abstractmethod
    async def get_deduplication_estimate(
        self,
        collection_id: UUID,
        kg_deduplication_settings: KGEntityDeduplicationSettings,
    ) -> KGDeduplicationEstimationResponse:
        """Get deduplication cost estimate."""
        pass

    # Other operations
    @abstractmethod
    async def create_vector_index(self) -> None:
        """Create vector index."""
        raise NotImplementedError

    @abstractmethod
    async def delete_triples(self, triple_ids: list[int]) -> None:
        """Delete triples."""
        raise NotImplementedError

    @abstractmethod
    async def get_schema(self) -> Any:
        """Get schema."""
        raise NotImplementedError

    @abstractmethod
    async def structured_query(self) -> Any:
        """Perform structured query."""
        raise NotImplementedError

    @abstractmethod
    async def update_extraction_prompt(self) -> None:
        """Update extraction prompt."""
        raise NotImplementedError

    @abstractmethod
    async def update_kg_search_prompt(self) -> None:
        """Update KG search prompt."""
        raise NotImplementedError

    @abstractmethod
    async def upsert_triples(self) -> None:
        """Upsert triples."""
        raise NotImplementedError

    @abstractmethod
    async def get_existing_entity_extraction_ids(
        self, document_id: UUID
    ) -> list[str]:
        """Get existing entity extraction IDs."""
        raise NotImplementedError

    @abstractmethod
    async def get_all_triples(self, collection_id: UUID) -> List[Triple]:
        raise NotImplementedError

    @abstractmethod
    async def update_entity_descriptions(self, entities: list[Entity]):
        raise NotImplementedError


class PromptHandler(Handler):
    """Abstract base class for prompt handling operations."""

    @abstractmethod
    async def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> None:
        """Add a new prompt template to the database."""
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
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        """Get an overview of stored files."""
        pass


class LoggingHandler(Handler):
    """Abstract base class defining the interface for logging handlers."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the logging handler and create necessary tables."""
        pass

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
        self, run_ids: List[UUID], limit_per_run: int = 10
    ) -> List[Dict]:
        """Retrieve logs for specified run IDs."""
        pass

    @abstractmethod
    async def get_info_logs(
        self,
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[List[UUID]] = None,
    ) -> List[RunInfoLog]:
        """Retrieve run information logs with filtering options."""
        pass

    # Conversation management methods
    @abstractmethod
    async def create_conversation(self) -> str:
        """Create a new conversation and return its ID."""
        pass

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all associated data."""
        pass

    @abstractmethod
    async def get_conversations_overview(
        self,
        conversation_ids: Optional[List[UUID]] = None,
        offset: int = 0,
        limit: int = -1,
    ) -> Dict[str, Union[List[Dict], int]]:
        """Get an overview of conversations with pagination."""
        pass

    # Message management methods
    @abstractmethod
    async def add_message(
        self,
        conversation_id: str,
        content: Message,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
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
    ) -> List[Tuple[str, Message]]:
        """Retrieve all messages in a conversation branch."""
        pass

    # Branch management methods
    @abstractmethod
    async def get_branches_overview(self, conversation_id: str) -> List[Dict]:
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
    collection_handler: CollectionHandler
    token_handler: TokenHandler
    user_handler: UserHandler
    vector_handler: VectorHandler
    kg_handler: KGHandler
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

    async def get_chunk(self, extraction_id: UUID) -> Optional[dict[str, Any]]:
        return await self.vector_handler.get_chunk(extraction_id)

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

    async def add_kg_extractions(
        self,
        kg_extractions: list[KGExtraction],
        table_prefix: str = "chunk_",
    ) -> Tuple[int, int]:
        """Forward to KG handler add_kg_extractions method."""
        return await self.kg_handler.add_kg_extractions(
            kg_extractions, table_prefix
        )

    async def add_entities(
        self,
        entities: list[Entity],
        table_name: str,
        conflict_columns: list[str] = [],
    ) -> Any:
        """Forward to KG handler add_entities method."""
        return await self.kg_handler.add_entities(
            entities, table_name, conflict_columns
        )

    async def add_triples(
        self,
        triples: list[Triple],
        table_name: str = "chunk_triple",
    ) -> None:
        """Forward to KG handler add_triples method."""
        return await self.kg_handler.add_triples(triples, table_name)

    async def get_entity_map(
        self, offset: int, limit: int, document_id: UUID
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Forward to KG handler get_entity_map method."""
        return await self.kg_handler.get_entity_map(offset, limit, document_id)

    async def upsert_embeddings(
        self,
        data: List[Tuple[Any]],
        table_name: str,
    ) -> None:
        """Forward to KG handler upsert_embeddings method."""
        return await self.kg_handler.upsert_embeddings(data, table_name)

    # Community methods
    async def add_communities(self, communities: List[Any]) -> None:
        """Forward to KG handler add_communities method."""
        return await self.kg_handler.add_communities(communities)

    async def get_communities(
        self,
        collection_id: UUID,
        offset: int = 0,
        limit: int = 100,
        levels: Optional[list[int]] = None,
        community_numbers: Optional[list[int]] = None,
    ) -> dict:
        """Forward to KG handler get_communities method."""
        return await self.kg_handler.get_communities(
            collection_id, offset, limit, levels, community_numbers
        )

    async def get_community_count(self, collection_id: UUID) -> int:
        """Forward to KG handler get_community_count method."""
        return await self.kg_handler.get_community_count(collection_id)

    async def add_community_report(
        self, community_report: CommunityReport
    ) -> None:
        """Forward to KG handler add_community_report method."""
        return await self.kg_handler.add_community_report(community_report)

    async def get_community_details(
        self, community_number: int, collection_id: UUID
    ) -> Tuple[int, list[Entity], list[Triple]]:
        """Forward to KG handler get_community_details method."""
        return await self.kg_handler.get_community_details(
            community_number, collection_id
        )

    async def get_community_reports(
        self, collection_id: UUID
    ) -> List[CommunityReport]:
        """Forward to KG handler get_community_reports method."""
        return await self.kg_handler.get_community_reports(collection_id)

    async def check_community_reports_exist(
        self, collection_id: UUID, offset: int, limit: int
    ) -> List[int]:
        """Forward to KG handler check_community_reports_exist method."""
        return await self.kg_handler.check_community_reports_exist(
            collection_id, offset, limit
        )

    async def perform_graph_clustering(
        self,
        collection_id: UUID,
        leiden_params: Dict[str, Any],
    ) -> int:
        """Forward to KG handler perform_graph_clustering method."""
        return await self.kg_handler.perform_graph_clustering(
            collection_id, leiden_params
        )

    # Graph operations
    async def delete_graph_for_collection(
        self, collection_id: UUID, cascade: bool = False
    ) -> None:
        """Forward to KG handler delete_graph_for_collection method."""
        return await self.kg_handler.delete_graph_for_collection(
            collection_id, cascade
        )

    async def delete_node_via_document_id(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        """Forward to KG handler delete_node_via_document_id method."""
        return await self.kg_handler.delete_node_via_document_id(
            document_id, collection_id
        )

    # Entity and Triple operations
    async def get_entities(
        self,
        collection_id: UUID,
        offset: int = 0,
        limit: int = -1,
        entity_ids: Optional[List[str]] = None,
        entity_names: Optional[List[str]] = None,
        entity_table_name: str = "document_entity",
    ) -> dict:
        """Forward to KG handler get_entities method."""
        return await self.kg_handler.get_entities(
            collection_id,
            offset,
            limit,
            entity_ids,
            entity_names,
            entity_table_name,
        )

    async def get_triples(
        self,
        collection_id: UUID,
        offset: int = 0,
        limit: int = 100,
        entity_names: Optional[List[str]] = None,
        triple_ids: Optional[List[str]] = None,
    ) -> dict:
        """Forward to KG handler get_triples method."""
        return await self.kg_handler.get_triples(
            collection_id, offset, limit, entity_names, triple_ids
        )

    async def get_entity_count(
        self,
        collection_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
        distinct: bool = False,
        entity_table_name: str = "document_entity",
    ) -> int:
        """Forward to KG handler get_entity_count method."""
        return await self.kg_handler.get_entity_count(
            collection_id, document_id, distinct, entity_table_name
        )

    async def get_triple_count(
        self,
        collection_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
    ) -> int:
        """Forward to KG handler get_triple_count method."""
        return await self.kg_handler.get_triple_count(
            collection_id, document_id
        )

    # Estimation methods
    async def get_creation_estimate(
        self, collection_id: UUID, kg_creation_settings: KGCreationSettings
    ) -> KGCreationEstimationResponse:
        """Forward to KG handler get_creation_estimate method."""
        return await self.kg_handler.get_creation_estimate(
            collection_id, kg_creation_settings
        )

    async def get_enrichment_estimate(
        self, collection_id: UUID, kg_enrichment_settings: KGEnrichmentSettings
    ) -> KGEnrichmentEstimationResponse:
        """Forward to KG handler get_enrichment_estimate method."""
        return await self.kg_handler.get_enrichment_estimate(
            collection_id, kg_enrichment_settings
        )

    async def get_deduplication_estimate(
        self,
        collection_id: UUID,
        kg_deduplication_settings: KGEntityDeduplicationSettings,
    ) -> KGDeduplicationEstimationResponse:
        """Forward to KG handler get_deduplication_estimate method."""
        return await self.kg_handler.get_deduplication_estimate(
            collection_id, kg_deduplication_settings
        )

    async def get_all_triples(self, collection_id: UUID) -> List[Triple]:
        return await self.kg_handler.get_all_triples(collection_id)

    async def update_entity_descriptions(self, entities: list[Entity]):
        return await self.kg_handler.update_entity_descriptions(entities)

    async def vector_query(
        self, query: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        return self.kg_handler.vector_query(query, **kwargs)  # type: ignore

    async def create_vector_index(self) -> None:
        return await self.kg_handler.create_vector_index()

    async def delete_triples(self, triple_ids: list[int]) -> None:
        return await self.kg_handler.delete_triples(triple_ids)

    async def get_schema(self) -> Any:
        return await self.kg_handler.get_schema()

    async def structured_query(self) -> Any:
        return await self.kg_handler.structured_query()

    async def update_extraction_prompt(self) -> None:
        return await self.kg_handler.update_extraction_prompt()

    async def update_kg_search_prompt(self) -> None:
        return await self.kg_handler.update_kg_search_prompt()

    async def upsert_triples(self) -> None:
        return await self.kg_handler.upsert_triples()

    async def get_existing_entity_extraction_ids(
        self, document_id: UUID
    ) -> list[str]:
        return await self.kg_handler.get_existing_entity_extraction_ids(
            document_id
        )

    async def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> None:
        return await self.prompt_handler.add_prompt(
            name, template, input_types
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
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        return await self.file_handler.get_files_overview(
            filter_document_ids, filter_file_names, offset, limit
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
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[List[UUID]] = None,
    ) -> List[RunInfoLog]:
        """Retrieve log info entries with filtering and pagination."""
        return await self.logging_handler.get_info_logs(
            offset, limit, run_type_filter, user_ids
        )

    async def get_logs(
        self,
        run_ids: List[UUID],
        limit_per_run: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve logs for specified run IDs with a per-run limit."""
        return await self.logging_handler.get_logs(run_ids, limit_per_run)
