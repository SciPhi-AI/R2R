"""Base classes for knowledge graph providers."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple

from ...base.utils.base_utils import RelationshipType
from ..abstractions.graph import Entity, KGExtraction, Triple
from ..abstractions.llm import GenerationConfig
from ..abstractions.restructure import KGCreationSettings, KGEnrichmentSettings
from .base import ProviderConfig

logger = logging.getLogger(__name__)


class KGConfig(ProviderConfig):
    """A base KG config class"""

    provider: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    url: Optional[str] = None
    database: Optional[str] = None

    batch_size: Optional[int] = 1
    kg_extraction_prompt: Optional[str] = "few_shot_ner_kg_extraction"
    kg_search_prompt: Optional[str] = "kg_search"
    kg_search_config: Optional[GenerationConfig] = None
    kg_store_path: Optional[str] = None
    kg_enrichment_settings: Optional[KGEnrichmentSettings] = (
        KGEnrichmentSettings()
    )
    kg_creation_settings: Optional[KGCreationSettings] = KGCreationSettings()

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return [None, "neo4j", "local"]


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
        self.config.validate()

    @property
    @abstractmethod
    def client(self) -> Any:
        """Get client."""
        pass

    @abstractmethod
    def get(self, subj: str) -> list[list[str]]:
        """Abstract method to get triplets."""
        pass

    @abstractmethod
    def get_rel_map(
        self,
        subjs: Optional[list[str]] = None,
        depth: int = 2,
        limit: int = 30,
    ) -> dict[str, list[list[str]]]:
        """Abstract method to get depth-aware rel map."""
        pass

    @abstractmethod
    def upsert_entities(self, entities: list[Entity], *args, **kwargs) -> None:
        """Abstract method to add triplet."""
        pass

    @abstractmethod
    def upsert_triples(self, triples: list[Triple]) -> None:
        """Abstract method to add triplet."""
        pass

    @abstractmethod
    def get_entities(
        self,
        entity_ids: list[str] | None = None,
        with_description: bool = False,
    ) -> list[Entity]:
        """Abstract method to get entities."""
        pass

    @abstractmethod
    def get_triples(self, triple_ids: list[str] | None = None) -> list[Triple]:
        """Abstract method to get triples."""
        pass

    @abstractmethod
    def upsert_nodes_and_relationships(
        self, kg_extractions: list[KGExtraction]
    ) -> None:
        """Abstract method to add triplet."""
        pass

    @abstractmethod
    def delete(self, subj: str, rel: str, obj: str) -> None:
        """Abstract method to delete triplet."""
        pass

    @abstractmethod
    def get_schema(self, refresh: bool = False) -> str:
        """Abstract method to get the schema of the graph store."""
        pass

    @abstractmethod
    def structured_query(
        self, query: str, param_map: Optional[dict[str, Any]] = None
    ) -> Any:
        """Abstract method to query the graph store with statement and parameters."""
        if param_map is None:
            param_map = {}

    @abstractmethod
    def vector_query(
        self, query, **kwargs: Any
    ) -> Tuple[list[Entity], list[float]]:
        """Abstract method to query the graph store with a vector store query."""

    # TODO - Type this method.
    @abstractmethod
    def update_extraction_prompt(
        self,
        prompt_provider: Any,
        entity_types: list[Any],
        relationship_types: list[RelationshipType],
    ):
        """Abstract method to update the KG extraction prompt."""
        pass

    # TODO - Type this method.
    @abstractmethod
    def update_kg_search_prompt(
        self,
        prompt_provider: Any,
        entity_types: list[Any],
        relationship_types: list[RelationshipType],
    ):
        """Abstract method to update the KG agent prompt."""
        pass

    @abstractmethod
    def create_vector_index(
        self, node_type: str, node_property: str, dimension: int
    ) -> None:
        """Abstract method to create a vector index."""
        pass


def escape_braces(s: str) -> str:
    """
    Escape braces in a string.
    This is a placeholder function - implement the actual logic as needed.
    """
    # Implement your escape_braces logic here
    return s.replace("{", "{{").replace("}", "}}")
