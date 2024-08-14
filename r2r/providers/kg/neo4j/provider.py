import json
import os
from typing import Any, Dict, List, Optional, Tuple
import neo4j
import time
import time
from datetime import datetime, date
import uuid
from decimal import Decimal

from .graph_queries import (
    PUT_CHUNKS_QUERY,
    GET_CHUNKS_QUERY,
    UNIQUE_CONSTRAINTS, 
    PUT_ENTITIES_QUERY, 
    PUT_TRIPLES_QUERY, 
    PUT_COMMUNITIES_QUERY, 
    PUT_COMMUNITIES_REPORT_QUERY,
    PUT_COVARIATES_QUERY,
    GET_ENTITIES_QUERY,
    GET_TRIPLES_QUERY,
    GET_COMMUNITIES_QUERY,
    GET_COMMUNITIES_REPORT_QUERY,
    GET_COVARIATES_QUERY
)

from r2r.base import (
    EntityType,
    RelationshipType,
    Fragment,
    KGConfig,
    KGProvider,
    PromptProvider,
    format_entity_types,
    format_relations,
    Community,
)


from r2r.base.abstractions.graph import (
    Entity,
    Triple,
    KGExtraction,
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
        return self._driver.execute_query(
            query, parameters_=param_map
        )

    def convert_to_neo4j_compatible(self, value):
        if isinstance(value, (str, int, float, bool)):
            return value
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, uuid.UUID):
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
            {k: self.convert_to_neo4j_compatible(v) for k, v in item.dict().items()}
            for item in model_list
        ]

    def batched_import(self, statement, df, batch_size=1000):
        """
        Import a dataframe into Neo4j using a batched approach.
        Parameters: statement is the Cypher query to execute, df is the dataframe to import, and batch_size is the number of rows to import in each batch.
        """
        total = len(df)
        start_s = time.time()
        for start in range(0,total, batch_size):
            batch = df[start: min(start+batch_size,total)]
            batch = self.convert_model_list_to_neo4j_compatible(batch)
            result = self._driver.execute_query("UNWIND $rows AS value " + statement, 
                                        rows=batch,
                                        database_=self._database)
            print(result.summary.counters)
        print(f'{total} rows in { time.time() - start_s} s.')    
        return total

    def get_chunks(self, chunk_ids: List[str] = None) -> List[Fragment]:
        """
        Get chunks from the graph.
        """
        return self.structured_query(GET_CHUNKS_QUERY, chunk_ids)

    def upsert_chunks(self, chunks: List[Fragment]):
        """
        Upsert chunks into the graph.
        """
        return self.batched_import(PUT_CHUNKS_QUERY, chunks)

        # create constraints, idempotent operation
    def upsert_entities(self, entities: List[Entity]):
        """
        Upsert entities into the graph.
        """
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
        self.batched_import(PUT_COMMUNITIES_QUERY, communities)


    def get_entities(self, entity_ids: List[str] = []) -> List[Entity]:
        """
        Get entities from the graph.
        """
        return self.structured_query(GET_ENTITIES_QUERY, {"entity_ids": entity_ids})
    

    def upsert_nodes_and_relationships(self, kg_extractions: list[KGExtraction]) -> None:

        all_entities = []
        all_relationships = []
        for extraction in kg_extractions:
            all_entities.extend(extraction.entities)
            all_relationships.extend(extraction.triples)

        nodes_upserted = self.upsert_entities(all_entities)
        relationships_upserted = self.upsert_triples(all_relationships)

        return nodes_upserted, relationships_upserted

    def get(self, entity_name: str = None) -> Entity:
        """
        Get entities from the graph.
        """
        return self.db_query(GET_ENTITIES_QUERY, entity_name)
    
    def get_triples(self, triple_ids: list[str] | None = None) -> list[Triple]:
        """
        Get triples from the graph.
        """
        neo4j_records = self.structured_query(GET_TRIPLES_QUERY, {"triple_ids": triple_ids})
        triples = [Triple(subject=record['e1']._properties['value'],
                          predicate=record['rel'].type,
                          object=record['e2']._properties['value'],
                          **record['rel']._properties)
                   for record in neo4j_records.records]
        return triples

    def update_extraction_prompt(self, prompt_provider: Any, entity_types: list[Any], relations: list[RelationshipType]) -> None:
        pass


    def update_kg_search_prompt(self, prompt_provider: Any, entity_types: list[Any], relations: list[RelationshipType]) -> None:
        pass

    def get_communities(self) -> List[Community]:
        """
        Get communities from the graph.
        """
        return self.db_query(GET_COMMUNITIES_QUERY)
    

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


    def client(self):
        return self._driver
    

    def get_rel_map(self, graph_nodes: Any, depth: int = 2, limit: int = 30, ignore_rels: Optional[List[str]] = None) -> List[Triple]:
        pass

    def get_schema(self, refresh: bool = False) -> str:
        return super().get_schema(refresh)
    

    def retrieve_cache(self, cache_type: str, cache_id: str) -> bool:
        return super().retrieve_cache(cache_type, cache_id)
    

    def vector_query(self, query, **kwargs: Any) -> Tuple[list[Entity], list[float]]:
        pass