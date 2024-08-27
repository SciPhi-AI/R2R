import json
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from core.base import KGConfig, KGProvider
from core.base.abstractions.document import DocumentFragment
from core.base.abstractions.graph import (
    Community,
    Entity,
    KGExtraction,
    RelationshipType,
    Triple,
)

from .graph_queries import (
    GET_CHUNKS_QUERY,
    GET_COMMUNITIES_QUERY,
    GET_ENTITIES_QUERY,
    GET_TRIPLES_BY_SUBJECT_AND_OBJECT_QUERY,
    GET_TRIPLES_QUERY,
    PUT_CHUNKS_QUERY,
    PUT_COMMUNITIES_QUERY,
    PUT_ENTITIES_EMBEDDINGS_QUERY,
    PUT_ENTITIES_QUERY,
    PUT_TRIPLES_QUERY,
    UNIQUE_CONSTRAINTS,
)


class Neo4jKGProvider(KGProvider):

    def __init__(self, config: KGConfig, *args: Any, **kwargs: Any) -> None:

        try:
            import neo4j
        except ImportError:
            raise ImportError("Please install neo4j: pip install neo4j")

        username = config.extra_fields.get("user", None) or os.getenv(
            "NEO4J_USER"
        )
        password = config.extra_fields.get("password", None) or os.getenv(
            "NEO4J_PASSWORD"
        )
        url = config.extra_fields.get("url", None) or os.getenv("NEO4J_URL")
        database = config.extra_fields.get("database", None) or os.getenv(
            "NEO4J_DATABASE", "neo4j"
        )

        if not username or not password or not url:
            raise ValueError(
                "Neo4j configuration values are missing. Please set NEO4J_USER, NEO4J_PASSWORD, and NEO4J_URL environment variables."
            )

        self._driver = neo4j.GraphDatabase.driver(
            url, auth=(username, password), **kwargs
        )
        self._async_driver = neo4j.AsyncGraphDatabase.driver(
            url,
            auth=(username, password),
            **kwargs,
        )
        self._database = database
        self.structured_schema = {}
        self.config = config

        self.create_constraints()
        super().__init__(config, *args, **kwargs)

    @property
    def client(self):
        return self._driver

    def create_constraints(self):
        for statement in UNIQUE_CONSTRAINTS:
            self._driver.execute_query(statement)

    def structured_query(self, query: str, param_map: Dict[str, Any] = {}):
        return self._driver.execute_query(query, parameters_=param_map)

    def convert_to_neo4j_compatible(self, value):
        if isinstance(value, (str, int, float, bool)):
            return value
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, UUID):
            return str(value)
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, list):
            return value
        elif isinstance(value, dict):
            return json.dumps(value)
        else:
            return str(value)

    def convert_model_list_to_neo4j_compatible(self, model_list):
        return [
            {
                k: self.convert_to_neo4j_compatible(v)
                for k, v in item.dict().items()
            }
            for item in model_list
        ]

    def get_entity_map(
        self, entity_names: list[str] | None = None
    ) -> dict[str, list[Any]]:
        entities = self.get(entity_names)
        triples = self.get_triples(entity_names)
        entity_map = {}
        for entity in entities:
            if entity.name not in entity_map:
                entity_map[entity.name] = {"entities": [], "triples": []}
            entity_map[entity.name]["entities"].append(entity)

        for triple in triples:
            if triple.subject in entity_map:
                entity_map[triple.subject]["triples"].append(triple)
            if triple.object in entity_map:
                entity_map[triple.object]["triples"].append(triple)
        return entity_map

    def batched_import(self, statement, df, batch_size=1000):
        """
        Import a dataframe into Neo4j using a batched approach.
        Parameters: statement is the Cypher query to execute, df is the dataframe to import, and batch_size is the number of rows to import in each batch.
        """
        total = len(df)
        results = []
        for start in range(0, total, batch_size):
            batch = df[start : min(start + batch_size, total)]
            batch = self.convert_model_list_to_neo4j_compatible(batch)
            result = self._driver.execute_query(
                "UNWIND $rows AS value " + statement,
                rows=batch,
                database_=self._database,
            )
            results.append(result)
        return results

    def get_chunks(
        self, chunk_ids: List[str] = None
    ) -> List[DocumentFragment]:
        """
        Get chunks from the graph.
        """
        return self.structured_query(GET_CHUNKS_QUERY, chunk_ids)

    def upsert_chunks(self, chunks: List[DocumentFragment]):
        """
        Upsert chunks into the graph.
        """
        return self.batched_import(PUT_CHUNKS_QUERY, chunks)

        # create constraints, idempotent operation

    def upsert_entities(
        self, entities: List[Entity], with_embeddings: bool = False
    ):
        """
        Upsert entities into the graph.
        """
        if with_embeddings:
            return self.batched_import(PUT_ENTITIES_EMBEDDINGS_QUERY, entities)
        else:
            return self.batched_import(PUT_ENTITIES_QUERY, entities)

    def upsert_triples(self, triples: List[Triple]):
        """
        Upsert relations into the graph.
        """
        return self.batched_import(PUT_TRIPLES_QUERY, triples)

    def upsert_communities(self, communities: List[Community]):
        """
        Upsert communities into the graph.
        """
        return self.batched_import(PUT_COMMUNITIES_QUERY, communities)

    def get_entities(self, entity_ids: List[str] = []) -> List[Entity]:
        """
        Get entities from the graph.
        """
        neo4j_records = self.structured_query(
            GET_ENTITIES_QUERY, {"entity_ids": entity_ids}
        )
        entities = [
            Entity(
                category=", ".join(list(record["e"]._labels)[1:]),
                **record["e"]._properties,
            )
            for record in neo4j_records.records
        ]
        return entities

    def upsert_nodes_and_relationships(
        self, kg_extractions: list[KGExtraction]
    ) -> Tuple[int, int]:

        all_entities = []
        all_relationships = []
        for extraction in kg_extractions:
            all_entities.extend(list(extraction.entities.values()))
            all_relationships.extend(extraction.triples)

        nodes_upserted = self.upsert_entities(all_entities)
        relationships_upserted = self.upsert_triples(all_relationships)

        return (len(nodes_upserted), len(relationships_upserted))

    def get(self, entity_name: str = None) -> Entity:
        """
        Get entities from the graph.
        """
        if entity_name is None:
            return self.get_entities()
        else:
            return self.get_entities(entity_ids=[entity_name])

    def get_triples(self, triple_ids: list[str] | None = None) -> list[Triple]:
        """
        Get triples from the graph.
        """

        if triple_ids is None:
            neo4j_records = self.structured_query(GET_TRIPLES_QUERY)
        else:
            triple_ids = [triple_id.split("->") for triple_id in triple_ids]
            triple_ids = [
                {
                    "subject": triple_id[0],
                    "predicate": triple_id[1],
                    "object": triple_id[2],
                }
                for triple_id in triple_ids
            ]
            neo4j_records = self.structured_query(
                GET_TRIPLES_BY_SUBJECT_AND_OBJECT_QUERY,
                {"triples": triple_ids},
            )

        triples = [
            Triple(
                subject=record["e1"]._properties["name"],
                predicate=record["rel"].type,
                object=record["e2"]._properties["name"],
                **record["rel"]._properties,
            )
            for record in neo4j_records.records
        ]
        return triples

    def update_extraction_prompt(
        self,
        prompt_provider: Any,
        entity_types: list[Any],
        relations: list[RelationshipType],
    ) -> None:
        pass

    def update_kg_search_prompt(
        self,
        prompt_provider: Any,
        entity_types: list[Any],
        relations: list[RelationshipType],
    ) -> None:
        pass

    def get_communities(self, level: str = None) -> List[Community]:
        """
        Get communities from the graph.
        """
        neo4j_records = self.structured_query(
            GET_COMMUNITIES_QUERY, {"level": level}
        )

        communities = [
            Community(**record["c"]._properties, id=record["c"]["community"])
            for record in neo4j_records.records
        ]
        return communities

    def delete_all_nodes(self):
        self._driver.execute_query("MATCH (a)-[r]->(b) DELETE a, r, b")
        self._driver.execute_query("MATCH (a) DELETE a")

    def delete(
        self,
        entity_names: Optional[List[str]] = None,
        relation_names: Optional[List[str]] = None,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        pass

    def get_rel_map(
        self,
        graph_nodes: Any,
        depth: int = 2,
        limit: int = 30,
        ignore_rels: Optional[List[str]] = None,
    ) -> List[Triple]:
        pass

    def create_vector_index(
        self, node_type: str, node_property: str, dimension: int
    ) -> None:

        query = f"""
        CREATE VECTOR INDEX `{node_type}_{node_property}` IF NOT EXISTS

        FOR (n:{node_type}) ON n.{node_property}
        OPTIONS {{indexConfig: {{`vector.similarity_function`: 'cosine', `vector.dimensions`:{dimension}}}}}"""

        self.structured_query(query)

    def get_schema(self, refresh: bool = False) -> str:
        return super().get_schema(refresh)

    def retrieve_cache(self, cache_type: str, cache_id: str) -> bool:
        return False

    def vector_query(self, query, **kwargs: Any) -> Dict[str, Any]:

        query_embedding = kwargs.get("query_embedding", None)
        search_type = kwargs.get("search_type", "__Entity__")
        embedding_type = kwargs.get("embedding_type", "description_embedding")
        property_names = kwargs.get(
            "property_names", ["name", "description", "summary"]
        )
        limit = kwargs.get("limit", 10)

        if search_type == "__Relationship__":

            query = f"""
                MATCH () - [e] -> ()
                WHERE e.{embedding_type} IS NOT NULL AND size(e.{embedding_type}) = $dimension
                WITH e, vector.similarity.cosine(e.{embedding_type}, $embedding) AS score
                ORDER BY score DESC LIMIT toInteger($limit)
                RETURN e, score
            """

            query_params = {
                "embedding": query_embedding,
                "dimension": len(query_embedding),
                "limit": limit,
            }

        else:
            query = f"""
                MATCH (e:{search_type})
                WHERE e.{embedding_type} IS NOT NULL AND size(e.{embedding_type}) = $dimension
                WITH e, vector.similarity.cosine(e.{embedding_type}, $embedding) AS score
                ORDER BY score DESC LIMIT toInteger($limit)
                RETURN e, score
            """
            query_params = {
                "embedding": query_embedding,
                "dimension": len(query_embedding),
                "limit": limit,
                "search_type": search_type,
            }

        neo4j_results = self.structured_query(query, query_params)

        # get the descriptions from the neo4j results
        # descriptions = [record['e']._properties[property_name] for record in neo4j_results.records for property_name in property_names]
        # return descriptions, scores

        ret = {}
        for record in neo4j_results.records:
            ret[record["e"]._properties["name"]] = {}

            for property_name in property_names:
                if property_name in record["e"]._properties:
                    ret[record["e"]._properties["name"]][property_name] = (
                        record["e"]._properties[property_name]
                    )

        return ret
