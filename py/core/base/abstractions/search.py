"""Abstractions for search functionality."""

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .llm import GenerationConfig


class VectorSearchResult(BaseModel):
    """Result of a search operation."""

    fragment_id: UUID
    extraction_id: UUID
    document_id: UUID
    user_id: Optional[UUID]
    collection_ids: list[UUID]
    score: float
    text: str
    metadata: dict[str, Any]

    def __str__(self) -> str:
        return f"VectorSearchResult(fragment_id={self.fragment_id}, extraction_id={self.extraction_id}, document_id={self.document_id}, score={self.score})"

    def __repr__(self) -> str:
        return self.__str__()

    def dict(self) -> dict:
        return {
            "fragment_id": self.fragment_id,
            "extraction_id": self.extraction_id,
            "document_id": self.document_id,
            "user_id": self.user_id,
            "collection_ids": self.collection_ids,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
        }

    class Config:
        json_schema_extra = {
            "fragment_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
            "extraction_id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
            "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
            "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
            "collection_ids": [],
            "score": 0.23943702876567796,
            "text": "Example text from the document",
            "metadata": {
                "title": "example_document.pdf",
                "associated_query": "What is the capital of France?",
            },
        }


class KGLocalSearchResult(BaseModel):
    """Result of a local knowledge graph search operation."""

    query: str
    entities: dict[str, Any]
    relationships: dict[str, Any]
    communities: dict[str, Any]

    def __str__(self) -> str:
        return f"KGLocalSearchResult(query={self.query}, entities={self.entities}, relationships={self.relationships}, communities={self.communities})"

    def __repr__(self) -> str:
        return self.__str__()

    class Config:
        json_schema_extra = {
            "query": "Who is Aristotle?",
            "entities": {
                "0": {
                    "name": "Aristotle",
                    "description": "Aristotle was an ancient Greek philosopher and polymath, recognized as the father of various fields including logic, biology, and political science. He authored significant works such as the *Nicomachean Ethics* and *Politics*, where he explored concepts of virtue, governance, and the nature of reality, while also critiquing Platos ideas. His teachings and observations laid the groundwork for numerous disciplines, influencing thinkers ...",
                }
            },
            "relationships": {},
            "communities": {
                "0": {
                    "summary": {
                        "title": "Aristotle and His Contributions",
                        "summary": "The community revolves around Aristotle, an ancient Greek philosopher and polymath, who made significant contributions to various fields including logic, biology, political science, and economics. His works, such as 'Politics' and 'Nicomachean Ethics', have influenced numerous disciplines and thinkers from antiquity through the Middle Ages and beyond. The relationships between his various works and the fields he contributed to highlight his profound impact on Western thought.",
                        "rating": 9.5,
                        "rating_explanation": "The impact severity rating is high due to Aristotle's foundational influence on multiple disciplines and his enduring legacy in Western philosophy and science.",
                        "findings": [
                            {
                                "summary": "Aristotle's Foundational Role in Logic",
                                "explanation": "Aristotle is credited with the earliest study of formal logic, and his conception of it was the dominant form of Western logic until the 19th-century advances in mathematical logic. His works compiled into a set of six books ...",
                            }
                        ],
                    }
                }
            },
        }


class KGGlobalSearchResult(BaseModel):
    """Result of a global knowledge graph search operation."""

    query: str
    search_result: list[str]

    def __str__(self) -> str:
        return f"KGGlobalSearchResult(query={self.query}, search_result={self.search_result})"

    def __repr__(self) -> str:
        return self.__str__()

    def dict(self) -> dict:
        return {"query": self.query, "search_result": self.search_result}

    class Config:
        json_schema_extra = {
            "query": "What were Aristotles key contributions to philosophy?",
            "search_result": [
                "### Aristotle's Key Contributions to Philosophy\n\n"
                "Aristotle's extensive body of work laid the foundation for numerous fields within philosophy and beyond, "
                "significantly shaping the trajectory of Western thought. His systematic approach to data collection and "
                "analysis has had a lasting impact on modern scientific methods. Below, we explore some of his most "
                "influential contributions.\n\n"
                "#### Foundational Works and Systematic Approach\n\n"
                "Aristotle's writings cover a broad spectrum of topics, including logic, biology, ethics, and political science. "
                "His key works such as 'Physics,' 'On the Soul,' and 'Nicomachean Ethics' delve into fundamental concepts "
                "like substance, memory, and the nature of the city [Data: Reports (1, 2, 3, 4, 5, +more)]. These texts not "
                "only provided a comprehensive framework for understanding various aspects of the natural and human world "
                "but also established methodologies that continue to influence contemporary scientific inquiry.\n\n"
                "#### Ethical and Political Philosophy\n\n"
                "In 'Nicomachean Ethics,' Aristotle explores the concept of a virtuous character, emphasizing the importance "
                "of moral virtues and the development of good habits. His work 'Politics' further examines the structure and "
                "function of the city (polis), addressing issues related to property, trade, and governance. Aristotle's "
                "classification of political constitutions and his definition of the city as the natural political community "
                "have had a profound and enduring impact on political thought [Data: Reports (11, 12); Triples (21, 22, 23, 24, 25)].\n\n"
                "#### Theories on Memory and Perception\n\n"
                "Aristotle's theories on memory and perception are articulated in his works 'On the Soul' and 'De Anima iii 3.' "
                "He defines memory as the retention of experiences shaped by sensation and discusses the faculty of imagination "
                "(phantasia). These theories have significantly influenced subsequent philosophical and psychological studies "
                "on cognition and perception [Data: Reports (13, 14); Triples (26, 27, 28, 29, 30)].\n\n"
                "#### Epistemology and Scientific Method\n\n"
                "Aristotle's epistemology, known as immanent realism, is based on the study of things that exist or happen in "
                "the world. This approach emphasizes empirical observation and has been instrumental in shaping the development "
                "of scientific methods. His insistence on grounding knowledge in observable phenomena laid the groundwork for "
                "future empirical research [Data: Reports (3)].\n\n"
                "#### Engagement with Predecessors and Contemporaries\n\n"
                "Aristotle was also known for his critical engagement with the ideas of his predecessors and contemporaries. "
                "For instance, he refuted Democritus's claim about the Milky Way and criticized Empedocles's materialist theory "
                "of 'survival of the fittest.' These critiques highlight Aristotle's active participation in the broader "
                "philosophical discourse of his time and his contributions to refining and advancing philosophical thought "
                "[Data: Reports (15, 16); Triples (31, 32, 33, 34, 35)].\n\n"
                "### Conclusion\n\n"
                "Aristotle's contributions to philosophy are vast and multifaceted, encompassing ethics, politics, epistemology, "
                "and more. His works continue to be studied and revered for their depth, rigor, and enduring relevance. Through "
                "his systematic approach and critical engagement with existing ideas, Aristotle has left an indelible mark on "
                "the landscape of Western philosophy."
            ],
        }


class KGSearchResult(BaseModel):
    """Result of a knowledge graph search operation."""

    local_result: Optional[KGLocalSearchResult] = None
    global_result: Optional[KGGlobalSearchResult] = None

    def __str__(self) -> str:
        return f"KGSearchResult(local_result={self.local_result}, global_result={self.global_result})"

    def __repr__(self) -> str:
        return self.__str__()

    def dict(self) -> dict:
        return {
            "local_result": (
                self.local_result.dict() if self.local_result else None
            ),
            "global_result": (
                self.global_result.dict() if self.global_result else None
            ),
        }

    class Config:
        json_schema_extra = {
            "local_result": KGLocalSearchResult.Config.json_schema_extra,
            "global_result": KGGlobalSearchResult.Config.json_schema_extra,
        }


class AggregateSearchResult(BaseModel):
    """Result of an aggregate search operation."""

    vector_search_results: Optional[list[VectorSearchResult]]
    kg_search_results: Optional[list[KGSearchResult]] = None

    def __str__(self) -> str:
        return f"AggregateSearchResult(vector_search_results={self.vector_search_results}, kg_search_results={self.kg_search_results})"

    def __repr__(self) -> str:
        return f"AggregateSearchResult(vector_search_results={self.vector_search_results}, kg_search_results={self.kg_search_results})"

    def dict(self) -> dict:
        return {
            "vector_search_results": (
                [result.dict() for result in self.vector_search_results]
                if self.vector_search_results
                else []
            ),
            "kg_search_results": self.kg_search_results or None,
        }


# TODO - stop duplication of this enum, move collections primitives to 'abstractions'
class IndexMeasure(str, Enum):
    """
    An enum representing the types of distance measures available for indexing.

    Attributes:
        cosine_distance (str): The cosine distance measure for indexing.
        l2_distance (str): The Euclidean (L2) distance measure for indexing.
        max_inner_product (str): The maximum inner product measure for indexing.
    """

    cosine_distance = "cosine_distance"
    l2_distance = "l2_distance"
    max_inner_product = "max_inner_product"


class HybridSearchSettings(BaseModel):
    full_text_weight: float = Field(
        default=1.0, description="Weight to apply to full text search"
    )
    semantic_weight: float = Field(
        default=5.0, description="Weight to apply to semantic search"
    )
    full_text_limit: int = Field(
        default=200,
        description="Maximum number of results to return from full text search",
    )
    rrf_k: int = Field(
        default=50, description="K-value for RRF (Rank Reciprocal Fusion)"
    )


class VectorSearchSettings(BaseModel):
    use_vector_search: bool = Field(
        default=True, description="Whether to use vector search"
    )
    use_hybrid_search: bool = Field(
        default=False,
        description="Whether to perform a hybrid search (combining vector and keyword search)",
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filters to apply to the vector search",
    )
    search_limit: int = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=1_000,
    )
    selected_collection_ids: list[UUID] = Field(
        default_factory=list,
        description="Group IDs to search for",
    )
    index_measure: IndexMeasure = Field(
        default=IndexMeasure.cosine_distance,
        description="The distance measure to use for indexing",
    )
    include_values: bool = Field(
        default=True,
        description="Whether to include search score values in the search results",
    )
    include_metadatas: bool = Field(
        default=True,
        description="Whether to include element metadata in the search results",
    )
    probes: Optional[int] = Field(
        default=10,
        description="Number of ivfflat index lists to query. Higher increases accuracy but decreases speed.",
    )
    ef_search: Optional[int] = Field(
        default=40,
        description="Size of the dynamic candidate list for HNSW index search. Higher increases accuracy but decreases speed.",
    )
    hybrid_search_settings: Optional[HybridSearchSettings] = Field(
        default=HybridSearchSettings(),
        description="Settings for hybrid search",
    )
    search_strategy: Optional[str] = Field(
        default="vanilla",
        description="Search strategy to use (e.g., 'default', 'query_fusion', 'hyde')",
    )

    class Config:
        json_encoders = {UUID: str}
        json_schema_extra = {
            "use_vector_search": True,
            "use_hybrid_search": True,
            "filters": {"category": "technology"},
            "search_limit": 20,
            "selected_collection_ids": [
                "2acb499e-8428-543b-bd85-0d9098718220",
                "3e157b3a-8469-51db-90d9-52e7d896b49b",
            ],
            "index_measure": "cosine_distance",
            "include_metadata": True,
            "probes": 10,
            "ef_search": 40,
            "hybrid_search_settings": {
                "full_text_weight": 1.0,
                "semantic_weight": 5.0,
                "full_text_limit": 200,
                "rrf_k": 50,
            },
        }

    def model_dump(self, *args, **kwargs):
        dump = super().model_dump(*args, **kwargs)
        dump["selected_collection_ids"] = [
            str(uuid) for uuid in dump["selected_collection_ids"]
        ]
        return dump


class KGSearchSettings(BaseModel):
    use_kg_search: bool = False
    kg_search_type: str = "global"  # 'global' or 'local'
    kg_search_level: Optional[str] = None
    kg_search_generation_config: Optional[GenerationConfig] = Field(
        default_factory=GenerationConfig
    )
    # TODO: add these back in
    # entity_types: list = []
    # relationships: list = []
    max_community_description_length: int = 65536
    max_llm_queries_for_global_search: int = 250
    local_search_limits: dict[str, int] = {
        "__Entity__": 20,
        "__Relationship__": 20,
        "__Community__": 20,
    }

    class Config:
        json_encoders = {UUID: str}
        json_schema_extra = {
            "use_kg_search": True,
            "kg_search_type": "global",
            "kg_search_level": "0",
            "kg_search_generation_config": GenerationConfig.Config.json_schema_extra,
            "max_community_description_length": 65536,
            "max_llm_queries_for_global_search": 250,
            "local_search_limits": {
                "__Entity__": 20,
                "__Relationship__": 20,
                "__Community__": 20,
            },
        }
