"""Base classes for knowledge graph providers."""

import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Tuple

from ..abstractions.llama_abstractions import EntityNode, LabelledNode
from ..abstractions.llama_abstractions import Relation as LlamaRelation
from ..abstractions.llama_abstractions import VectorStoreQuery
from .base import ProviderConfig
from .prompt import PromptProvider

if TYPE_CHECKING:
    from r2r.main import R2RClient

from ...base.utils.base_utils import EntityType, Relation
from ..abstractions.llm import GenerationConfig

logger = logging.getLogger(__name__)


class KGConfig(ProviderConfig):
    """A base KG config class"""

    provider: Optional[str] = None
    batch_size: int = 1
    kg_extraction_prompt: Optional[str] = "few_shot_ner_kg_extraction"
    kg_search_prompt: Optional[str] = "kg_search"
    kg_extraction_config: Optional[GenerationConfig] = None

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return [None, "neo4j"]


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
    def upsert_nodes(self, nodes: list[EntityNode]) -> None:
        """Abstract method to add triplet."""
        pass

    @abstractmethod
    def upsert_relations(self, relations: list[LlamaRelation]) -> None:
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
        self, query: str, param_map: Optional[dict[str, Any]] = {}
    ) -> Any:
        """Abstract method to query the graph store with statement and parameters."""
        pass

    @abstractmethod
    def vector_query(
        self, query: VectorStoreQuery, **kwargs: Any
    ) -> Tuple[list[LabelledNode], list[float]]:
        """Abstract method to query the graph store with a vector store query."""

    # TODO - Type this method.
    @abstractmethod
    def update_extraction_prompt(
        self,
        prompt_provider: Any,
        entity_types: list[Any],
        relations: list[Relation],
    ):
        """Abstract method to update the KG extraction prompt."""
        pass

    # TODO - Type this method.
    @abstractmethod
    def update_kg_search_prompt(
        self,
        prompt_provider: Any,
        entity_types: list[Any],
        relations: list[Relation],
    ):
        """Abstract method to update the KG agent prompt."""
        pass


def escape_braces(s: str) -> str:
    """
    Escape braces in a string.
    This is a placeholder function - implement the actual logic as needed.
    """
    # Implement your escape_braces logic here
    return s.replace("{", "{{").replace("}", "}}")


# TODO - Make this more configurable / intelligent
def update_kg_prompt(
    client: "R2RClient",
    r2r_prompts: PromptProvider,
    prompt_base: str,
    entity_types: list[EntityType],
    relations: list[Relation],
) -> None:
    # TODO - DO NOT HARD CODE THIS!
    if len(entity_types) > 10:
        raise ValueError(
            "Too many entity types to update prompt, limited to 10"
        )
    if len(relations) > 20:
        raise ValueError("Too many relations to update prompt, limited to 20")
    # Get the default extraction template
    template_name: str = f"{prompt_base}_with_spec"

    new_template: str = r2r_prompts.get_prompt(
        template_name,
        {
            "entity_types": json.dumps(
                {
                    "entity_types": [
                        str(entity.name.replace(" ", "_").upper())
                        for entity in entity_types
                    ]
                },
                indent=4,
            ),
            "relations": json.dumps(
                {
                    "predicates": [
                        str(relation.name.replace(" ", "_").upper())
                        for relation in relations
                    ]
                },
                indent=4,
            ),
            "input": """\n{input}""",
        },
    )

    # Escape all braces in the template, except for the {input} placeholder, for formatting
    escaped_template: str = escape_braces(new_template).replace(
        """{{input}}""", """{input}"""
    )

    # Update the client's prompt
    client.update_prompt(
        prompt_base,
        template=escaped_template,
        input_types={"input": "str"},
    )
