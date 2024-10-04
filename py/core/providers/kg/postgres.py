import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import asyncpg

from core.base import (
    CommunityReport,
    DatabaseProvider,
    EmbeddingProvider,
    Entity,
    KGConfig,
    KGExtraction,
    KGExtractionStatus,
    KGProvider,
    Triple,
)
from shared.abstractions import (
    KGCreationSettings,
    KGEnrichmentSettings,
    KGRunType,
)
from shared.api.models.kg.responses import (
    KGCreationEstimationResponse,
    KGEnrichmentEstimationResponse,
)
from shared.utils import llm_cost_per_million_tokens

logger = logging.getLogger(__name__)


class PostgresKGProvider(KGProvider):

    def __init__(
        self,
        config: KGConfig,
        db_provider: DatabaseProvider,
        embedding_provider: EmbeddingProvider,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, *args, **kwargs)

        self.db_provider = db_provider.relational
        self.embedding_provider = embedding_provider
        try:
            import networkx as nx

            self.nx = nx
        except ImportError as exc:
            raise ImportError(
                "NetworkX is not installed. Please install it to use this module."
            ) from exc

    async def initialize(self):
        logger.info(
            f"Initializing PostgresKGProvider for project {self.db_provider.project_name}"
        )
        await self.create_tables(project_name=self.db_provider.project_name)

    async def execute_query(
        self, query: str, params: Optional[list[Any]] = None
    ) -> Any:
        return await self.db_provider.execute_query(query, params)

    async def execute_many(
        self,
        query: str,
        params: Optional[list[tuple[Any]]] = None,
        batch_size: int = 1000,
    ) -> Any:
        return await self.db_provider.execute_many(query, params, batch_size)

    async def fetch_query(
        self,
        query: str,
        params: Optional[Any] = None,  # TODO: make this strongly typed
    ) -> Any:
        return await self.db_provider.fetch_query(query, params)

    def _get_table_name(self, base_name: str) -> str:
        return self.db_provider._get_table_name(base_name)

    async def create_tables(self, project_name: str):
        # raw entities table
        # create schema

        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("entity_raw")} (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            extraction_ids UUID[] NOT NULL,
            document_id UUID NOT NULL,
            attributes JSONB
        );
        """
        await self.execute_query(query)

        # raw triples table, also the final table. this will have embeddings.
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("triple_raw")} (
            id SERIAL PRIMARY KEY,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            weight FLOAT NOT NULL,
            description TEXT NOT NULL,
            embedding vector({self.embedding_provider.config.base_dimension}),
            extraction_ids UUID[] NOT NULL,
            document_id UUID NOT NULL,
            attributes JSONB NOT NULL
        );
        """
        await self.execute_query(query)

        # entity description table, unique by document_id, category, name
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("entity_description")} (
            id SERIAL PRIMARY KEY,
            document_id UUID NOT NULL,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            description_embedding vector(1536),
            extraction_ids UUID[] NOT NULL,
            attributes JSONB NOT NULL,
            UNIQUE (document_id, category, name)
        );"""

        await self.execute_query(query)

        # triples table 2 # Relationship summaries by document ID
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("triple_description")} (
            id SERIAL PRIMARY KEY,
            document_ids UUID[] NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            weight FLOAT NOT NULL,
            description TEXT NOT NULL,
            extraction_ids UUID[] NOT NULL,
            attributes JSONB NOT NULL,
            UNIQUE (document_ids, subject, predicate, object)
        );"""

        await self.execute_query(query)

        # embeddings tables
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("entity_embedding")} (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            extraction_ids UUID[] NOT NULL,
            description_embedding vector({self.embedding_provider.config.base_dimension}) NOT NULL,
            document_id UUID NOT NULL,
            UNIQUE (name, document_id)
            );
        """

        await self.execute_query(query)

        # TODO: Create another table for entity_embedding_collection
        # entity embeddings at a collection level

        # communities table, result of the Leiden algorithm
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("community")} (
            id SERIAL PRIMARY KEY,
            node TEXT NOT NULL,
            cluster INT NOT NULL,
            parent_cluster INT,
            level INT NOT NULL,
            is_final_cluster BOOLEAN NOT NULL,
            triple_ids INT[] NOT NULL,
            collection_id UUID NOT NULL
        );"""

        await self.execute_query(query)

        # communities_report table
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("community_report")} (
            id SERIAL PRIMARY KEY,
            community_number INT NOT NULL,
            collection_id UUID NOT NULL,
            level INT NOT NULL,
            name TEXT NOT NULL,
            summary TEXT NOT NULL,
            findings TEXT[] NOT NULL,
            rating FLOAT NOT NULL,
            rating_explanation TEXT NOT NULL,
            embedding vector({self.embedding_provider.config.base_dimension}) NOT NULL,
            attributes JSONB,
            UNIQUE (community_number, level, collection_id)
        );"""

        await self.execute_query(query)

    async def _add_objects(
        self, objects: list[Any], table_name: str
    ) -> asyncpg.Record:
        """
        Upsert objects into the specified table.
        """
        # Get non-null attributes from the first object
        non_null_attrs = {
            k: v for k, v in objects[0].__dict__.items() if v is not None
        }
        columns = ", ".join(non_null_attrs.keys())

        placeholders = ", ".join(f"${i+1}" for i in range(len(non_null_attrs)))

        QUERY = f"""
            INSERT INTO {self._get_table_name(table_name)} ({columns})
            VALUES ({placeholders})
        """

        # Filter out null values for each object
        params = [
            tuple(
                json.dumps(v) if isinstance(v, dict) else v
                for v in obj.__dict__.values()
                if v is not None
            )
            for obj in objects
        ]
        return await self.execute_many(QUERY, params)

    async def add_entities(
        self,
        entities: list[Entity],
        table_name: str,
    ) -> asyncpg.Record:
        """
        Upsert entities into the entities_raw table. These are raw entities extracted from the document.

        Args:
            entities: list[Entity]: list of entities to upsert
            collection_name: str: name of the collection

        Returns:
            result: asyncpg.Record: result of the upsert operation
        """
        return await self._add_objects(entities, table_name)

    async def add_triples(
        self,
        triples: list[Triple],
        table_name: str = "triples",
    ) -> None:
        """
        Upsert triples into the triple_raw table. These are raw triples extracted from the document.

        Args:
            triples: list[Triple]: list of triples to upsert
            table_name: str: name of the table to upsert into

        Returns:
            result: asyncpg.Record: result of the upsert operation
        """
        return await self._add_objects(triples, table_name)

    async def add_kg_extractions(
        self,
        kg_extractions: list[KGExtraction],
        table_suffix: str = "_raw",
    ) -> Tuple[int, int]:
        """
        Upsert entities and triples into the database. These are raw entities and triples extracted from the document fragments.

        Args:
            kg_extractions: list[KGExtraction]: list of KG extractions to upsert
            table_suffix: str: suffix to add to the table names

        Returns:
            total_entities: int: total number of entities upserted
            total_relationships: int: total number of relationships upserted
        """

        total_entities, total_relationships = 0, 0

        for extraction in kg_extractions:

            total_entities, total_relationships = (
                total_entities + len(extraction.entities),
                total_relationships + len(extraction.triples),
            )

            if extraction.entities:
                if not extraction.entities[0].extraction_ids:
                    for i in range(len(extraction.entities)):
                        extraction.entities[i].extraction_ids = (
                            extraction.extraction_ids
                        )
                        extraction.entities[i].document_id = (
                            extraction.document_id
                        )

                await self.add_entities(
                    extraction.entities,
                    table_name="entity" + table_suffix,
                )

            if extraction.triples:
                if not extraction.triples[0].extraction_ids:
                    for i in range(len(extraction.triples)):
                        extraction.triples[i].extraction_ids = (
                            extraction.extraction_ids
                        )
                    extraction.triples[i].document_id = extraction.document_id

                await self.add_triples(
                    extraction.triples,
                    table_name="triple" + table_suffix,
                )

        return (total_entities, total_relationships)

    async def get_entity_map(
        self, offset: int, limit: int, document_id: UUID
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:

        QUERY1 = f"""
            WITH entities_list AS (
                SELECT DISTINCT name
                FROM {self._get_table_name("entity_raw")}
                WHERE document_id = $1
                ORDER BY name ASC
                LIMIT {limit} OFFSET {offset}
            )
            SELECT e.name, e.description, e.category,
                   (SELECT array_agg(DISTINCT x) FROM unnest(e.extraction_ids) x) AS extraction_ids,
                   e.document_id
            FROM {self._get_table_name("entity_raw")} e
            JOIN entities_list el ON e.name = el.name
            GROUP BY e.name, e.description, e.category, e.extraction_ids, e.document_id
            ORDER BY e.name;"""

        entities_list = await self.fetch_query(QUERY1, [document_id])
        entities_list = [
            Entity(
                name=entity["name"],
                description=entity["description"],
                category=entity["category"],
                extraction_ids=entity["extraction_ids"],
                document_id=entity["document_id"],
            )
            for entity in entities_list
        ]

        QUERY2 = f"""
            WITH entities_list AS (

                SELECT DISTINCT name
                FROM {self._get_table_name("entity_raw")}
                WHERE document_id = $1
                ORDER BY name ASC
                LIMIT {limit} OFFSET {offset}
            )

            SELECT DISTINCT t.subject, t.predicate, t.object, t.weight, t.description,
                   (SELECT array_agg(DISTINCT x) FROM unnest(t.extraction_ids) x) AS extraction_ids, t.document_id
            FROM {self._get_table_name("triple_raw")} t
            JOIN entities_list el ON t.subject = el.name
            ORDER BY t.subject, t.predicate, t.object;
        """

        triples_list = await self.fetch_query(QUERY2, [document_id])
        triples_list = [
            Triple(
                subject=triple["subject"],
                predicate=triple["predicate"],
                object=triple["object"],
                weight=triple["weight"],
                description=triple["description"],
                extraction_ids=triple["extraction_ids"],
                document_id=triple["document_id"],
            )
            for triple in triples_list
        ]

        entity_map: Dict[str, Dict[str, List[Any]]] = {}
        for entity in entities_list:
            if entity.name not in entity_map:
                entity_map[entity.name] = {"entities": [], "triples": []}
            entity_map[entity.name]["entities"].append(entity)

        for triple in triples_list:
            if triple.subject in entity_map:
                entity_map[triple.subject]["triples"].append(triple)
            if triple.object in entity_map:
                entity_map[triple.object]["triples"].append(triple)

        return entity_map

    async def upsert_embeddings(
        self,
        data: List[Tuple[Any]],
        table_name: str,
    ) -> None:
        QUERY = f"""
            INSERT INTO {self._get_table_name(table_name)} (name, description, description_embedding, extraction_ids, document_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (name, document_id) DO UPDATE SET
                description = EXCLUDED.description,
                description_embedding = EXCLUDED.description_embedding,
                extraction_ids = EXCLUDED.extraction_ids,
                document_id = EXCLUDED.document_id
            """
        return await self.execute_many(QUERY, data)

    async def upsert_entities(self, entities: List[Entity]) -> None:
        QUERY = """
            INSERT INTO $1.$2 (category, name, description, description_embedding, extraction_ids, document_id, attributes)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """

        table_name = self._get_table_name("entities")
        query = QUERY.format(table_name)
        await self.execute_query(query, entities)

    async def upsert_relationships(self, relationships: list[Triple]) -> None:
        QUERY = """
            INSERT INTO $1.$2 (source, target, relationship)
            VALUES ($1, $2, $3)
            """

        table_name = self._get_table_name("triples")
        query = QUERY.format(table_name)
        await self.execute_query(query, relationships)

    async def vector_query(self, query: str, **kwargs: Any) -> Any:

        query_embedding = kwargs.get("query_embedding", None)
        search_type = kwargs.get("search_type", "__Entity__")
        embedding_type = kwargs.get("embedding_type", "description_embedding")
        property_names = kwargs.get("property_names", ["name", "description"])
        filters = kwargs.get("filters", {})
        limit = kwargs.get("limit", 10)

        table_name = ""
        if search_type == "__Entity__":
            table_name = "entity_embedding"
        elif search_type == "__Relationship__":
            table_name = "triple_raw"
        elif search_type == "__Community__":
            table_name = "community_report"
        else:
            raise ValueError(f"Invalid search type: {search_type}")

        property_names_str = ", ".join(property_names)

        collection_ids_dict = filters.get("collection_ids", {})
        filter_query = ""
        if collection_ids_dict:
            filter_query = "WHERE collection_id = ANY($3)"
            filter_ids = collection_ids_dict["$overlap"]

            if search_type == "__Community__":
                logger.info(f"Searching in collection ids: {filter_ids}")

            if (
                search_type == "__Entity__"
                or search_type == "__Relationship__"
            ):
                filter_query = "WHERE document_id = ANY($3)"
                query = f"""
                    SELECT distinct document_id FROM {self._get_table_name('document_info')} WHERE $1 = ANY(collection_ids)
                """
                filter_ids = [
                    doc_id["document_id"]
                    for doc_id in await self.fetch_query(query, filter_ids)
                ]
                logger.info(f"Searching in document ids: {filter_ids}")

        QUERY = f"""
            SELECT {property_names_str} FROM {self._get_table_name(table_name)} {filter_query} ORDER BY {embedding_type} <=> $1 LIMIT $2;
        """

        if filter_query != "":
            results = await self.fetch_query(
                QUERY, (str(query_embedding), limit, filter_ids)
            )
        else:
            results = await self.fetch_query(
                QUERY, (str(query_embedding), limit)
            )

        for result in results:
            yield {
                property_name: result[property_name]
                for property_name in property_names
            }

    async def get_all_triples(self, collection_id: UUID) -> List[Triple]:

        # getting all documents for a collection
        QUERY = f"""
            select distinct document_id from {self._get_table_name("document_info")} where $1 = ANY(collection_ids)
        """
        document_ids = await self.fetch_query(QUERY, [collection_id])
        document_ids = [doc_id["document_id"] for doc_id in document_ids]

        QUERY = f"""
            SELECT id, subject, predicate, weight, object FROM {self._get_table_name("triple_raw")} WHERE document_id = ANY($1)
        """
        triples = await self.fetch_query(QUERY, [document_ids])
        return [Triple(**triple) for triple in triples]

    async def add_communities(self, communities: List[Any]) -> None:
        QUERY = f"""
            INSERT INTO {self._get_table_name("community")} (node, cluster, parent_cluster, level, is_final_cluster, triple_ids, collection_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
        await self.execute_many(QUERY, communities)

    async def add_community_report(
        self, community_report: CommunityReport
    ) -> None:

        # TODO: Fix in the short term.
        # we need to do this because postgres insert needs to be a string
        community_report.embedding = str(community_report.embedding)  # type: ignore[assignment]

        non_null_attrs = {
            k: v for k, v in community_report.__dict__.items() if v is not None
        }
        columns = ", ".join(non_null_attrs.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(non_null_attrs)))

        conflict_columns = ", ".join(
            [f"{k} = EXCLUDED.{k}" for k in non_null_attrs.keys()]
        )

        QUERY = f"""
            INSERT INTO {self._get_table_name("community_report")} ({columns})
            VALUES ({placeholders})
            ON CONFLICT (community_number, level, collection_id) DO UPDATE SET
                {conflict_columns}
            """

        await self.execute_many(QUERY, [tuple(non_null_attrs.values())])

    async def perform_graph_clustering(
        self,
        collection_id: UUID,
        leiden_params: Dict[str, Any],
    ) -> int:
        """
        Leiden clustering algorithm to cluster the knowledge graph triples into communities.

        Available parameters and defaults:
            max_cluster_size: int = 1000,
            starting_communities: Optional[Dict[str, int]] = None,
            extra_forced_iterations: int = 0,
            resolution: Union[int, float] = 1.0,
            randomness: Union[int, float] = 0.001,
            use_modularity: bool = True,
            random_seed: Optional[int] = None,
            weight_attribute: str = "weight",
            is_weighted: Optional[bool] = None,
            weight_default: Union[int, float] = 1.0,
            check_directed: bool = True,
        """
        settings: Dict[str, Any] = {}
        triples = await self.get_all_triples(collection_id)

        logger.info(f"Clustering with settings: {str(settings)}")

        G = self.nx.Graph()
        for triple in triples:
            G.add_edge(
                triple.subject,
                triple.object,
                weight=triple.weight,
                id=triple.id,
            )

        hierarchical_communities = await self._compute_leiden_communities(
            G, leiden_params
        )

        def triple_ids(node: int) -> list[int]:
            # TODO: convert this to objects
            return [
                triple.id or i
                for i, triple in enumerate(triples)
                if triple.subject == node or triple.object == node
            ]

        # upsert the communities into the database.
        inputs = [
            (
                str(item.node),
                item.cluster,
                item.parent_cluster,
                item.level,
                item.is_final_cluster,
                triple_ids(item.node),
                collection_id,
            )
            for item in hierarchical_communities
        ]

        await self.add_communities(inputs)

        num_communities = len(
            set([item.cluster for item in hierarchical_communities])
        )

        return num_communities

    async def _compute_leiden_communities(
        self,
        graph: Any,
        leiden_params: Dict[str, Any],
    ) -> Any:
        """Compute Leiden communities."""
        try:
            from graspologic.partition import hierarchical_leiden

            if "random_seed" not in leiden_params:
                leiden_params["random_seed"] = (
                    7272  # add seed to control randomness
                )

            community_mapping = hierarchical_leiden(graph, **leiden_params)

            return community_mapping

        except ImportError as e:
            raise ImportError("Please install the graspologic package.") from e

    async def get_community_details(
        self, community_number: int
    ) -> Tuple[int, List[Dict[str, Any]], List[Dict[str, Any]]]:

        QUERY = f"""
            SELECT level FROM {self._get_table_name("community")} WHERE cluster = $1
            LIMIT 1
        """
        level = (await self.fetch_query(QUERY, [community_number]))[0]["level"]

        QUERY = f"""
            WITH node_triple_ids AS (

                SELECT node, triple_ids
                FROM {self._get_table_name("community")}
                WHERE cluster = $1
            )
            SELECT DISTINCT
                e.id AS id,
                e.name AS name,
                e.description AS description
            FROM node_triple_ids nti
            JOIN {self._get_table_name("entity_embedding")} e ON e.name = nti.node;
        """
        entities = await self.fetch_query(QUERY, [community_number])

        QUERY = f"""
            WITH node_triple_ids AS (

                SELECT node, triple_ids
                FROM {self._get_table_name("community")}
                WHERE cluster = $1
            )
            SELECT DISTINCT
                t.id, t.subject, t.predicate, t.object, t.weight, t.description
            FROM node_triple_ids nti
            JOIN {self._get_table_name("triple_raw")} t ON t.id = ANY(nti.triple_ids);
        """
        triples = await self.fetch_query(QUERY, [community_number])

        return level, entities, triples

    # async def client(self):
    #     return None

    async def get_community_reports(
        self, collection_id: UUID
    ) -> List[CommunityReport]:
        QUERY = f"""
            SELECT *c FROM {self._get_table_name("community_report")} WHERE collection_id = $1
        """
        return await self.fetch_query(QUERY, [collection_id])

    async def check_community_reports_exist(
        self, collection_id: UUID, offset: int, limit: int
    ) -> List[int]:
        QUERY = f"""
            SELECT distinct community_number FROM {self._get_table_name("community_report")} WHERE collection_id = $1 AND community_number >= $2 AND community_number < $3
        """
        community_numbers = await self.fetch_query(
            QUERY, [collection_id, offset, offset + limit]
        )
        return [item["community_number"] for item in community_numbers]

    async def delete_graph_for_collection(
        self, collection_id: UUID, cascade: bool = False
    ) -> None:

        # don't delete if status is PROCESSING.
        QUERY = f"""
            SELECT kg_enrichment_status FROM {self._get_table_name("collections")} WHERE collection_id = $1
        """
        status = (await self.fetch_query(QUERY, [collection_id]))[0][
            "kg_enrichment_status"
        ]
        if status == KGExtractionStatus.PROCESSING.value:
            return

        # remove all triples for these documents.
        QUERY = f"""
            DELETE FROM {self._get_table_name("community")} WHERE collection_id = $1;
            DELETE FROM {self._get_table_name("community_report")} WHERE collection_id = $1;
        """

        document_ids = await self.db_provider.documents_in_collection(
            collection_id
        )

        if cascade:
            QUERY += f"""
                DELETE FROM {self._get_table_name("entity_raw")} WHERE document_id = ANY($1);
                DELETE FROM {self._get_table_name("triple_raw")} WHERE document_id = ANY($1);
                DELETE FROM {self._get_table_name("entity_embedding")} WHERE document_id = ANY($1);
            """

        await self.execute_query(QUERY, [document_ids])

        # set status to PENDING for this collection.
        QUERY = f"""
            UPDATE {self._get_table_name("collections")} SET kg_enrichment_status = $1 WHERE collection_id = $2
        """
        await self.execute_query(
            QUERY, [KGExtractionStatus.PENDING, collection_id]
        )

    def _get_str_estimation_output(self, x: tuple[Any, Any]) -> str:
        if isinstance(x[0], int) and isinstance(x[1], int):
            return " - ".join(map(str, x))
        else:
            return " - ".join(f"{round(a, 2)}" for a in x)

    async def get_creation_estimate(
        self, collection_id: UUID, kg_creation_settings: KGCreationSettings
    ) -> KGCreationEstimationResponse:

        # todo: harmonize the document_id and id fields: postgres table contains document_id, but other places use id.
        document_ids = [
            doc.id
            for doc in (
                await self.db_provider.documents_in_collection(collection_id)
            )["results"]
        ]

        # TODO: Vecs schema naming got messed up somewhere.
        schema_name = self._get_table_name("document_chunks").split(".")[0]

        query = f"""
            SELECT document_id, COUNT(*) as chunk_count
            FROM {schema_name}.{schema_name}
            WHERE document_id = ANY($1)
            GROUP BY document_id
        """

        chunk_counts = await self.fetch_query(query, [document_ids])

        total_chunks = (
            sum(doc["chunk_count"] for doc in chunk_counts)
            // kg_creation_settings.extraction_merge_count
        )  # 4 chunks per llm
        estimated_entities = (
            total_chunks * 10,
            total_chunks * 20,
        )  # 25 entities per 4 chunks
        estimated_triples = (
            int(estimated_entities[0] * 1.25),
            int(estimated_entities[1] * 1.5),
        )  # Assuming 1.25 triples per entity on average

        estimated_llm_calls = (
            total_chunks * 2 + estimated_entities[0],
            total_chunks * 2 + estimated_entities[1],
        )

        total_in_out_tokens = (
            2000 * estimated_llm_calls[0] // 1000000,
            2000 * estimated_llm_calls[1] // 1000000,
        )  # in millions

        estimated_cost = (
            total_in_out_tokens[0]
            * llm_cost_per_million_tokens(
                kg_creation_settings.generation_config.model
            ),
            total_in_out_tokens[1]
            * llm_cost_per_million_tokens(
                kg_creation_settings.generation_config.model
            ),
        )

        total_time_in_minutes = (
            total_in_out_tokens[0] * 10 / 60,
            total_in_out_tokens[1] * 10 / 60,
        )  # 10 minutes per million tokens

        return KGCreationEstimationResponse(
            message='These are estimated ranges, actual values may vary. To run the KG creation process, run `create-graph` with `--run` in the cli, or `run_mode="run"` in the client.',
            document_count=len(document_ids),
            number_of_jobs_created=len(document_ids) + 1,
            total_chunks=total_chunks,
            estimated_entities=self._get_str_estimation_output(
                estimated_entities
            ),
            estimated_triples=self._get_str_estimation_output(
                estimated_triples
            ),
            estimated_llm_calls=self._get_str_estimation_output(
                estimated_llm_calls
            ),
            estimated_total_in_out_tokens_in_millions=self._get_str_estimation_output(
                total_in_out_tokens
            ),
            estimated_cost_in_usd=self._get_str_estimation_output(
                estimated_cost
            ),
            estimated_total_time_in_minutes="Depends on your API key tier. Accurate estimate coming soon. Rough estimate: "
            + self._get_str_estimation_output(total_time_in_minutes),
        )

    async def get_enrichment_estimate(
        self, collection_id: UUID, kg_enrichment_settings: KGEnrichmentSettings
    ) -> KGEnrichmentEstimationResponse:

        document_ids = [
            doc.id
            for doc in (
                await self.db_provider.documents_in_collection(collection_id)
            )["results"]
        ]

        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("entity_embedding")} WHERE document_id = ANY($1);
        """
        entity_count = (await self.fetch_query(QUERY, [document_ids]))[0][
            "count"
        ]

        if not entity_count:
            raise ValueError(
                "No entities found in the graph. Please run `create-graph` first."
            )

        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("triple_raw")} WHERE document_id = ANY($1);
        """
        triple_count = (await self.fetch_query(QUERY, [document_ids]))[0][
            "count"
        ]

        estimated_llm_calls = (entity_count // 10, entity_count // 5)
        estimated_total_in_out_tokens_in_millions = (
            2000 * estimated_llm_calls[0] / 1000000,
            2000 * estimated_llm_calls[1] / 1000000,
        )
        cost_per_million_tokens = llm_cost_per_million_tokens(
            kg_enrichment_settings.generation_config.model
        )
        estimated_cost = (
            estimated_total_in_out_tokens_in_millions[0]
            * cost_per_million_tokens,
            estimated_total_in_out_tokens_in_millions[1]
            * cost_per_million_tokens,
        )

        estimated_total_time = (
            estimated_total_in_out_tokens_in_millions[0] * 10 / 60,
            estimated_total_in_out_tokens_in_millions[1] * 10 / 60,
        )

        return KGEnrichmentEstimationResponse(
            message='These are estimated ranges, actual values may vary. To run the KG enrichment process, run `enrich-graph` with `--run` in the cli, or `run_mode="run"` in the client.',
            total_entities=entity_count,
            total_triples=triple_count,
            estimated_llm_calls=self._get_str_estimation_output(
                estimated_llm_calls
            ),
            estimated_total_in_out_tokens_in_millions=self._get_str_estimation_output(
                estimated_total_in_out_tokens_in_millions
            ),
            estimated_cost_in_usd=self._get_str_estimation_output(
                estimated_cost
            ),
            estimated_total_time_in_minutes="Depends on your API key tier. Accurate estimate coming soon. Rough estimate: "
            + self._get_str_estimation_output(estimated_total_time),
        )

    async def create_vector_index(self):
        # need to implement this. Just call vector db provider's create_vector_index method.
        # this needs to be run periodically for every collection.
        raise NotImplementedError

    async def delete_triples(self, triple_ids: list[int]):
        # need to implement this.
        raise NotImplementedError

    async def get_schema(self):
        # somehow get the rds from the postgres db.
        raise NotImplementedError

    async def get_entities(
        self,
        collection_id: UUID,
        offset: int = 0,
        limit: int = 100,
        entity_ids: Optional[List[str]] = None,
        with_description: bool = False,
    ) -> dict:
        conditions = []
        params = [collection_id]

        if entity_ids:
            conditions.append(f"id = ANY(${len(params) + 1})")
            params.append(entity_ids)

        params.extend([offset, limit])

        query = f"""
            SELECT id, name, category, description
            FROM {self._get_table_name("entity_raw")}
            WHERE document_id = ANY(
                SELECT document_id FROM {self._get_table_name("document_info")}
                WHERE $1 = ANY(collection_ids)
            )
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY id
            OFFSET ${len(params) - 1} LIMIT ${len(params)}
        """
        results = await self.fetch_query(query, params)
        total_entries = await self.get_entity_count(
            collection_id=collection_id
        )

        return {"results": results, "total_entries": total_entries}

    async def get_triples(
        self,
        collection_id: UUID,
        offset: int = 0,
        limit: int = 100,
        triple_ids: Optional[List[str]] = None,
    ) -> dict:
        conditions = []
        params = [str(collection_id)]

        if triple_ids:
            conditions.append(f"id = ANY(${len(params) + 1})")
            params.append([str(ele) for ele in triple_ids])  # type: ignore

        query = f"""
            SELECT id, subject, predicate, object
            FROM {self._get_table_name("triple_raw")}
            WHERE document_id = ANY(
                SELECT document_id FROM {self._get_table_name("document_info")}
                WHERE $1 = ANY(collection_ids)
            )
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY id
            OFFSET ${len(params) + 1} LIMIT ${len(params) + 2}
        """
        params.extend([str(offset), str(limit)])

        results = await self.fetch_query(query, params)
        total_entries = await self.get_triple_count(
            collection_id=collection_id
        )

        return {"results": results, "total_entries": total_entries}

    async def structured_query(self):
        raise NotImplementedError

    async def update_extraction_prompt(self):
        raise NotImplementedError

    async def update_kg_search_prompt(self):
        raise NotImplementedError

    async def upsert_triples(self):
        raise NotImplementedError

    async def get_entity_count(
        self,
        collection_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
    ) -> int:
        if collection_id is None and document_id is None:
            raise ValueError(
                "Either collection_id or document_id must be provided."
            )

        conditions = []
        params = []

        if collection_id:
            conditions.append(
                f"""
                document_id = ANY(
                    SELECT document_id FROM {self._get_table_name("document_info")}
                    WHERE $1 = ANY(collection_ids)
                )
                """
            )
            params.append(str(collection_id))
        else:
            conditions.append("document_id = $1")
            params.append(str(document_id))

        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("entity_raw")}
            WHERE {" AND ".join(conditions)}
        """
        return (await self.fetch_query(QUERY, params))[0]["count"]

    async def get_triple_count(
        self,
        collection_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
    ) -> int:
        if collection_id is None and document_id is None:
            raise ValueError(
                "Either collection_id or document_id must be provided."
            )

        conditions = []
        params = []

        if collection_id:
            conditions.append(
                f"""
                document_id = ANY(
                    SELECT document_id FROM {self._get_table_name("document_info")}
                    WHERE $1 = ANY(collection_ids)
                )
                """
            )
            params.append(str(collection_id))
        else:
            conditions.append("document_id = $1")
            params.append(str(document_id))

        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("triple_raw")}
            WHERE {" AND ".join(conditions)}
        """
        return (await self.fetch_query(QUERY, params))[0]["count"]
