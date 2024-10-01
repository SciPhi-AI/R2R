# type: ignore
import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from uuid import UUID

from core.base import KGConfig, KGProvider, R2RException
from core.base.abstractions import (
    Community,
    DocumentFragment,
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

logger = logging.getLogger(__name__)


class MemgraphKGProvider(KGProvider):
    """
    Memgraph Property Graph Store.

    This class implements support for Memgraph as a property graph store.
    Full details on the Github repository: https://github.com/memgraph/memgraph or website: https://memgraph.com/

    ```bash
    docker run -p 7687:7687 -p 3000:3000 memgraph/memgraph-mage:latest
    ```
    """

    def __init__(self, config: KGConfig, *args: Any, **kwargs: Any) -> None:

        try:
            # We could also use a pymgclient or GQLAlchemy
            import neo4j

        except ImportError:
            raise ImportError(
                "Please install a client that can connect to Memgraph client via: pip install neo4j"
            )

        username = config.user or os.getenv("MEMGRAPH_USER")
        password = config.password or os.getenv("MEMGRAPH_PASSWORD")
        url = config.url or os.getenv("MEMGRAPH_URL")

        database = config.database or os.getenv(
            "MEMGRAPH_DATABASE", "memgraph"
        )

        if not username or not password or not url:
            raise ValueError(
                "Memgraph configuration values are missing. Please set MEMGRAPH_USER, MEMGRAPH_PASSWORD, and MEMGRAPH_URL environment variables."
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
        Import a dataframe into Memgraph using a batched approach.
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

    def import_tripplets(self, statement, df, batch_size=1000):
        """
        Import a dataframe into Memgraph using a batched approach for tripplets.
        Parameters: statement is the Cypher query to execute, df is the dataframe to import, and batch_size is the number of rows to import in each batch.
        """
        total = len(df)
        results = []
        for start in range(0, total, batch_size):
            batch = df[start : min(start + batch_size, total)]
            batch = self.convert_model_list_to_neo4j_compatible(batch)
            for item in batch:
                params = {
                    "subject": item["subject"],
                    "object": item["object"],
                    "weight": item["weight"],
                    "description": item["description"],
                    "attributes": item["attributes"],
                    "text_unit_ids": item["text_unit_ids"],
                    "document_ids": item["document_ids"],
                }
                label = (
                    item["predicate"]
                    .upper()
                    .replace(" ", "_")
                    .replace("-", "_")
                )
                result = self._driver.execute_query(
                    statement.format(label=label),
                    parameters_=params,
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
        return self.import_tripplets(PUT_TRIPLES_QUERY, triples)

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
            all_entities.extend((list(extraction.entities.values())))
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
            memgraph_records = self.structured_query(GET_TRIPLES_QUERY)
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
            memgraph_records = self.structured_query(
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
            for record in memgraph_records.records
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
        self._driver.execute_query("MATCH (a) DETACH DELETE a")

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

    def get_schema(self, refresh: bool = False) -> str:
        return super().get_schema(refresh)

    def retrieve_cache(self, cache_type: str, cache_id: str) -> bool:
        return False

    def create_vector_index(
        self, node_type: str, node_property: str, dimension: int
    ) -> None:
        raise NotImplementedError("Functionality not yet implemented.")

    def vector_query(self, query, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("Functionality not yet implemented.")

    def perform_graph_clustering(
        self, leiden_params: dict
    ) -> Tuple[int, int, set[tuple[int, Any]]]:
        """
        Perform graph clustering on the graph.

        Input:
        - leiden_params: a dictionary that contains the parameters for the graph clustering.

        Output:
        - Total number of communities
        - Total number of hierarchies
        """
        
        # # step 1: drop the graph, if it exists and project the graph again.
        # # in this step the vertices that have no edges are not included in the projection.

        # GRAPH_EXISTS_QUERY = """
        #     CALL gds.graph.exists('kg_graph') YIELD exists
        #     WITH exists
        #     RETURN CASE WHEN exists THEN true ELSE false END as graphExists;

        # """

        # result = self.structured_query(GRAPH_EXISTS_QUERY)
        # graph_exists = result.records[0]["graphExists"]

        # GRAPH_PROJECTION_QUERY = """
        #     MATCH (s:__Entity__)-[r]->(t:__Entity__)
        #     RETURN gds.graph.project(
        #         'kg_graph',
        #         s,
        #         t,
        # """

        # if graph_exists:

        #     logger.info(f"Graph exists, dropping it")
        #     GRAPH_DROP_QUERY = (
        #         "CALL gds.graph.drop('kg_graph') YIELD graphName;"
        #     )
        #     result = self.structured_query(GRAPH_DROP_QUERY)

        #     GRAPH_PROJECTION_QUERY += """
        #         {
        #             sourceNodeProperties: s { },
        #             targetNodeProperties: t { },
        #             relationshipProperties: r { .weight }
        #         },
        #         {
        #             relationshipWeightProperty: 'weight',
        #             undirectedRelationshipTypes: ['*']
        #         }
        #     )
        #     """
        # else:
        #     GRAPH_PROJECTION_QUERY += """
        #         {
        #             sourceNodeProperties: s {},
        #             targetNodeProperties: t {},
        #             relationshipProperties: r { .weight }
        #         },
        #         {
        #             relationshipWeightProperty: 'weight',
        #             undirectedRelationshipTypes: ['*']
        #         }
        #     )"""

        # result = self.structured_query(GRAPH_PROJECTION_QUERY)

        # step 2: run the hierarchical leiden algorithm on the graph.
        # seed_property = leiden_params.get("seed_property", "communityIds")
        write_property = leiden_params.get("write_property", "communityIds")
        random_seed = leiden_params.get("random_seed", 42)
        include_intermediate_communities = leiden_params.get(
            "include_intermediate_communities", True
        )
        max_levels = leiden_params.get("max_levels", 10)
        gamma = leiden_params.get("gamma", 1.0)
        theta = leiden_params.get("theta", 0.01)
        tolerance = leiden_params.get("tolerance", 0.0001)
        min_community_size = leiden_params.get("min_community_size", 1)
        # don't use the seed property for now
        seed_property_config = (
            ""  # f"seedProperty: '{seed_property}'" if graph_exists else ""
        )
        
        #TODO: (@antejavor) Fix the modularities
        GRAPH_CLUSTERING_QUERY=f"""
        CALL leiden_community_detection.get() YIELD node, community_id, communities
        SET node.community_id = community_id
        SET node.communities = communities
        RETURN count(DISTINCT community_id) AS community_count
        """

        result = self.structured_query(GRAPH_CLUSTERING_QUERY).records[0]

        community_count: int = result["community_count"]
        # modularities = result["modularities"]

        logger.info(
            f"Performed graph clustering with {community_count} communities."
        )
        
        #TODO:(@antejavor) Fix intermediate communities 
        COMMUNITY_QUERY = f"""
            MATCH (n)
            WHERE n.communities IS NOT NULL
            RETURN DISTINCT
            CASE
                WHEN n.communities IS NOT NULL
                THEN n.communities
                ELSE []
            END AS community_ids
        """

        result = self.structured_query(COMMUNITY_QUERY)

        intermediate_communities = [
            record["community_ids"] for record in result.records
        ]

        intermediate_communities_set = set()
        for community_list in intermediate_communities:
            for level, community_id in enumerate(community_list):
                intermediate_communities_set.add((level, community_id))
        intermediate_communities_set = list(intermediate_communities_set)

        logger.info(
            f"Intermediate communities: {intermediate_communities_set}"
        )   
         #TODO:(@antejavor) Added community count instead of len(modularities), to force the signature
        return (
            community_count,
            community_count,
            intermediate_communities_set
            )

    def get_community_entities_and_triples(
        self, level: int, community_id: int, include_embeddings: bool = False
    ) -> Tuple[List[Entity], List[Triple]]:
        """
        Get the entities and triples that belong to a community.

        Input:
        - level: The level of the hierarchy.
        - community_id: The ID of the community to get the entities and triples for.
        - include_embeddings: Whether to include the embeddings in the output.

        Output:
        - A tuple of entities and triples that belong to the community.

        """

        # get the entities and triples from the graph
        query = """MATCH (a:__Entity__) - [r] -> (b:__Entity__)
                WHERE a.communities[$level] = $community_id
                OR b.communities[$level] = $community_id
                RETURN ID(a) AS source_id, a.name AS source, id(b) AS target_id, b.name AS target, a.description AS source_description,
                b.description AS target_description, labels(a) AS source_labels, labels(b) AS target_labels,
                r.description AS relationship_description, r.name AS relationship_name, r.weight AS relationship_weight, ID(r) AS relationship_id
        """

        neo4j_records = self.structured_query(
            query,
            {
                "community_id": int(community_id),
                "level": int(level),
            },
        )

        entities = [
            Entity(
                id=record["source_id"],
                name=record["source"],
                description=record["source_description"],
                category=", ".join(record["source_labels"]),
            )
            for record in neo4j_records.records
        ]

        triples = [
            Triple(
                id=record["relationship_id"],
                subject=record["source"],
                predicate=record["relationship_name"],
                object=record["target"],
                description=record["relationship_description"],
                weight=record["relationship_weight"],
            )
            for record in neo4j_records.records
        ]

        logger.info(
            f"{len(entities)} entities and {len(triples)} triples were retrieved for community {community_id} at level {level}"
        )

        return entities, triples
