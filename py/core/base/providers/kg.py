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
    KGExtraction,
    KGSearchSettings,
    RelationshipType,
    Triple,
)
from .base import ProviderConfig

logger = logging.getLogger(__name__)


# TODO - Bolt down types for KGConfig
class KGConfig(ProviderConfig):
    """A base KG config class"""

    provider: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    url: Optional[str] = None
    database: Optional[str] = None

    batch_size: Optional[int] = 1
    kg_store_path: Optional[str] = None
    kg_enrichment_settings: KGEnrichmentSettings = KGEnrichmentSettings()
    kg_creation_settings: KGCreationSettings = KGCreationSettings()
    kg_search_settings: KGSearchSettings = KGSearchSettings()

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["local", "postgres"]


class KGProvider(ABC):
    """An abstract class to provide a common interface for Knowledge Graphs."""

    def __init__(self, config: KGConfig) -> None:
        if not isinstance(config, KGConfig):
            raise ValueError(
                "KGProvider must be initialized with a `KGConfig`."
            )
        logger.info(f"Initializing KG provider with config: {config}")
        self.config = config
        self.validate_config()

    def validate_config(self) -> None:
        self.config.validate_config()

    @abstractmethod
    async def add_entities(
        self, entities: list[Entity], *args, **kwargs
    ) -> None:
        """Abstract method to add entities."""
        pass

    @abstractmethod
    async def add_triples(
        self, triples: list[Triple], table_name: str
    ) -> None:
        """Abstract method to add triples."""
        pass

    @abstractmethod
    async def add_kg_extractions(
        self, kg_extractions: list[KGExtraction], table_suffix: str = "_raw"
    ) -> Tuple[int, int]:
        """Abstract method to add KG extractions."""
        pass

    @abstractmethod
    async def get_entities(
        self,
        collection_id: UUID,
        offset: int,
        limit: int,
        entity_ids: list[str] | None = None,
        with_description: bool = False,
    ) -> list[Entity]:
        """Abstract method to get entities."""
        pass

    @abstractmethod
    async def get_triples(
        self,
        collection_id: UUID,
        offset: int,
        limit: int,
        triple_ids: list[str] | None = None,
    ) -> list[Triple]:
        """Abstract method to get triples."""
        pass

    @abstractmethod
    async def delete_triples(self, triple_ids: list[int]) -> None:
        """Abstract method to delete triples."""
        pass

    @abstractmethod
    async def get_schema(self, refresh: bool = False) -> str:
        """Abstract method to get the schema of the graph store."""
        pass

    @abstractmethod
    async def structured_query(
        self, query: str, param_map: Optional[dict[str, Any]] = None
    ) -> Any:
        """Abstract method to query the graph store with statement and parameters."""
        if param_map is None:
            param_map = {}

    @abstractmethod
    async def vector_query(
        self, query, **kwargs: Any
    ) -> Tuple[list[Entity], list[float]]:
        """Abstract method to query the graph store with a vector store query."""

    # TODO - Type this method.
    @abstractmethod
    async def update_extraction_prompt(
        self,
        prompt_provider: Any,
        entity_types: list[Any],
        relationship_types: list[RelationshipType],
    ):
        """Abstract method to update the KG extraction prompt."""
        pass

    # TODO - Type this method.
    @abstractmethod
    async def update_kg_search_prompt(
        self,
        prompt_provider: Any,
        entity_types: list[Any],
        relationship_types: list[RelationshipType],
    ):
        """Abstract method to update the KG agent prompt."""
        pass

    @abstractmethod
    async def create_vector_index(
        self, node_type: str, node_property: str, dimension: int
    ) -> None:
        """Abstract method to create a vector index."""
        pass

    @abstractmethod
    async def perform_graph_clustering(
        self,
        collection_id: UUID,
        leiden_params: dict,  # TODO - Add typing for leiden_params
    ) -> int:
        """Abstract method to perform graph clustering."""
        pass

    @abstractmethod
    async def get_entity_map(
        self, offset: int, limit: int, document_id: UUID
    ) -> dict[str, Any]:
        """Abstract method to get the entity map."""
        pass

    @abstractmethod
    async def get_community_details(self, community_number: int):
        """Abstract method to get community details."""
        pass

    @abstractmethod
    async def get_entity_count(
        self,
        collection_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
    ) -> int:
        """Abstract method to get the entity count."""
        pass

    @abstractmethod
    async def delete_graph_for_collection(
        self, collection_id: UUID, cascade: bool
    ) -> None:
        """Abstract method to delete the graph for a collection."""
        pass

    @abstractmethod
    async def get_creation_estimate(self, *args: Any, **kwargs: Any) -> Any:
        """Abstract method to get the creation estimate."""
        pass

    @abstractmethod
    async def get_enrichment_estimate(self, *args: Any, **kwargs: Any) -> Any:
        """Abstract method to get the enrichment estimate."""
        pass

    @abstractmethod
    async def add_community_report(
        self, community_report: CommunityReport
    ) -> None:
        """Abstract method to add a community report."""
        pass

    @abstractmethod
    async def get_community_reports(
        self, collection_id: UUID
    ) -> list[CommunityReport]:
        """Abstract method to get community reports."""
        pass

    @abstractmethod
    async def check_community_reports_exist(
        self, collection_id: UUID, offset: int, limit: int
    ) -> list[int]:
        """Abstract method to check if community reports exist."""
        pass


def escape_braces(s: str) -> str:
    """
    Escape braces in a string.
    This is a placeholder function - implement the actual logic as needed.
    """
    # Implement your escape_braces logic here
    return s.replace("{", "{{").replace("}", "}}")
