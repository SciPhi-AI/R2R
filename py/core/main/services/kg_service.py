import logging
import math
import time
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import HTTPException

from core.base import KGExtractionStatus, RunManager
from core.base.abstractions import (
    DataLevel,
    GenerationConfig,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEntityDeduplicationSettings,
    KGEntityDeduplicationType,
    R2RException,
    Entity,
    Relationship,
    Community,
    Graph,
)
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider
from core.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig
from .base import Service


logger = logging.getLogger()


async def _collect_results(result_gen: AsyncGenerator) -> list[dict]:
    results = []
    async for res in result_gen:
        results.append(res.json() if hasattr(res, "json") else res)
    return results


# TODO - Fix naming convention to read `KGService` instead of `KgService`
# this will require a minor change in how services are registered.
class KgService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipes: R2RPipes,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
        logging_connection: SqlitePersistentLoggingProvider,
    ):
        super().__init__(
            config,
            providers,
            pipes,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

    @telemetry_event("kg_relationships_extraction")
    async def kg_relationships_extraction(
        self,
        document_id: UUID,
        generation_config: GenerationConfig,
        extraction_merge_count: int,
        max_knowledge_relationships: int,
        entity_types: list[str],
        relation_types: list[str],
        **kwargs,
    ):
        try:

            logger.info(
                f"KGService: Processing document {document_id} for KG extraction"
            )

            await self.providers.database.set_workflow_status(
                id=document_id,
                status_type="kg_extraction_status",
                status=KGExtractionStatus.PROCESSING,
            )

            relationships = await self.pipes.kg_relationships_extraction_pipe.run(
                input=self.pipes.kg_relationships_extraction_pipe.Input(
                    message={
                        "document_id": document_id,
                        "generation_config": generation_config,
                        "extraction_merge_count": extraction_merge_count,
                        "max_knowledge_relationships": max_knowledge_relationships,
                        "entity_types": entity_types,
                        "relation_types": relation_types,
                        "logger": logger,
                    }
                ),
                state=None,
                run_manager=self.run_manager,
            )

            logger.info(
                f"KGService: Finished processing document {document_id} for KG extraction"
            )

            result_gen = await self.pipes.kg_storage_pipe.run(
                input=self.pipes.kg_storage_pipe.Input(message=relationships),
                state=None,
                run_manager=self.run_manager,
            )

        except Exception as e:
            logger.error(f"KGService: Error in kg_extraction: {e}")
            await self.providers.database.set_workflow_status(
                id=document_id,
                status_type="kg_extraction_status",
                status=KGExtractionStatus.FAILED,
            )
            raise e

        return await _collect_results(result_gen)

    @telemetry_event("create_entities")
    async def create_entities(
        self,
        entities: list[Entity],
    ):
        return await self.providers.database.graph_handler.entities.create(
            entities=entities,
        )

    @telemetry_event("list_entities")
    async def list_entities(
        self,
        level: DataLevel,
        id: UUID,
        offset: int,
        limit: int,
        entity_names: Optional[list[str]] = None,
        entity_categories: Optional[list[str]] = None,
        attributes: Optional[list[str]] = None,
        from_built_graph: Optional[bool] = False,
    ):
        return await self.providers.database.graph_handler.entities.get(
            level=level,
            id=id,
            entity_names=entity_names,
            entity_categories=entity_categories,
            attributes=attributes,
            offset=offset,
            limit=limit,
            from_built_graph=from_built_graph,
        )

    @telemetry_event("update_entity")
    async def update_entity_v3(
        self,
        entity: Entity,
    ):
        return await self.providers.database.graph_handler.entities.update(
            entity=entity,
        )

    @telemetry_event("delete_entity")
    async def delete_entity_v3(
        self,
        id: UUID,
        entity_id: UUID,
        level: DataLevel,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.entities.delete(
            id=id,
            entity_id=entity_id,
            level=level,
        )

    # TODO: deprecate this
    @telemetry_event("get_entities")
    async def get_entities(
        self,
        collection_id: Optional[UUID] = None,
        entity_ids: Optional[list[str]] = None,
        entity_table_name: str = "document_entity",
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.get_entities(
            collection_id=collection_id,
            entity_ids=entity_ids,
            entity_table_name=entity_table_name,
            offset=offset or 0,
            limit=limit or -1,
        )

    ################### RELATIONSHIPS ###################

    @telemetry_event("list_relationships_v3")
    async def list_relationships_v3(
        self,
        id: UUID,
        level: DataLevel,
        offset: int,
        limit: int,
        entity_names: Optional[list[str]] = None,
        relationship_types: Optional[list[str]] = None,
        attributes: Optional[list[str]] = None,
    ):
        return await self.providers.database.graph_handler.relationships.get(
            id=id,
            level=level,
            entity_names=entity_names,
            relationship_types=relationship_types,
            attributes=attributes,
            offset=offset,
            limit=limit,
        )

    @telemetry_event("create_relationships_v3")
    async def create_relationships_v3(
        self,
        relationships: list[Relationship],
        **kwargs,
    ):
        return (
            await self.providers.database.graph_handler.relationships.create(
                relationships
            )
        )

    @telemetry_event("delete_relationship_v3")
    async def delete_relationship_v3(
        self,
        level: DataLevel,
        id: UUID,
        relationship_id: UUID,
        **kwargs,
    ):
        return (
            await self.providers.database.graph_handler.relationships.delete(
                level=level,
                id=id,
                relationship_id=relationship_id,
            )
        )

    @telemetry_event("update_relationship_v3")
    async def update_relationship_v3(
        self,
        relationship: Relationship,
        **kwargs,
    ):
        return (
            await self.providers.database.graph_handler.relationships.update(
                relationship
            )
        )

    # TODO: deprecate this
    @telemetry_event("get_triples")
    async def get_relationships(
        self,
        collection_id: Optional[UUID] = None,
        entity_names: Optional[list[str]] = None,
        relationship_ids: Optional[list[str]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.get_relationships(
            collection_id=collection_id,
            entity_names=entity_names,
            relationship_ids=relationship_ids,
            offset=offset or 0,
            limit=limit or -1,
        )

    ################### COMMUNITIES ###################

    @telemetry_event("create_communities_v3")
    async def create_communities_v3(
        self,
        communities: list[Community],
        **kwargs,
    ):
        return await self.providers.database.graph_handler.communities.create(
            communities
        )

    @telemetry_event("update_community_v3")
    async def update_community_v3(
        self,
        community: Community,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.communities.update(
            community
        )

    @telemetry_event("delete_community_v3")
    async def delete_community_v3(
        self,
        community: Community,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.communities.delete(
            community
        )

    @telemetry_event("list_communities_v3")
    async def list_communities_v3(
        self,
        id: UUID,
        offset: int,
        limit: int,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.communities.get(
            id=id,
            offset=offset,
            limit=limit,
        )

    # TODO: deprecate this
    @telemetry_event("get_communities")
    async def get_communities(
        self,
        collection_id: Optional[UUID] = None,
        levels: Optional[list[int]] = None,
        community_numbers: Optional[list[int]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.get_communities(
            collection_id=collection_id,
            levels=levels,
            community_numbers=community_numbers,
            offset=offset or 0,
            limit=limit or -1,
        )

    ################### GRAPHS ###################

    @telemetry_event("create_new_graph")
    async def create_new_graph(self, graph: Graph) -> UUID:
        return await self.providers.database.graph_handler.create(graph)

    @telemetry_event("get_graphs")
    async def get_graphs(
        self, offset: int, limit: int, graph_id: Optional[UUID] = None
    ) -> Graph:
        return await self.providers.database.graph_handler.get(
            offset=offset, limit=limit, graph_id=graph_id
        )

    @telemetry_event("update_graph")
    async def update_graph(self, graph: Graph) -> UUID:
        return await self.providers.database.graph_handler.update(graph)

    @telemetry_event("delete_graph_v3")
    async def delete_graph_v3(self, id: UUID, cascade: bool = False) -> UUID:
        return await self.providers.database.graph_handler.delete(id, cascade)

    @telemetry_event("get_document_ids_for_create_graph")
    async def get_document_ids_for_create_graph(
        self,
        collection_id: UUID,
        force_kg_creation: bool,
        **kwargs,
    ):

        document_status_filter = [
            KGExtractionStatus.PENDING,
            KGExtractionStatus.FAILED,
        ]
        if force_kg_creation:
            document_status_filter += [
                KGExtractionStatus.PROCESSING,
            ]

        return await self.providers.database.get_document_ids_by_status(
            status_type="kg_extraction_status",
            status=[str(ele) for ele in document_status_filter],
            collection_id=collection_id,
        )

    @telemetry_event("kg_entity_description")
    async def kg_entity_description(
        self,
        document_id: UUID,
        max_description_input_length: int,
        **kwargs,
    ):

        start_time = time.time()

        logger.info(
            f"KGService: Running kg_entity_description for document {document_id}"
        )

        entity_count = (
            await self.providers.database.graph_handler.get_entity_count(
                document_id=document_id,
                distinct=True,
                entity_table_name="chunk_entity",
            )
        )

        logger.info(
            f"KGService: Found {entity_count} entities in document {document_id}"
        )

        # TODO - Do not hardcode the batch size,
        # make it a configurable parameter at runtime & server-side defaults

        # process 256 entities at a time
        num_batches = math.ceil(entity_count / 256)
        logger.info(
            f"Calling `kg_entity_description` on document {document_id} with an entity count of {entity_count} and total batches of {num_batches}"
        )
        all_results = []
        for i in range(num_batches):
            logger.info(
                f"KGService: Running kg_entity_description for batch {i+1}/{num_batches} for document {document_id}"
            )

            node_descriptions = await self.pipes.kg_entity_description_pipe.run(
                input=self.pipes.kg_entity_description_pipe.Input(
                    message={
                        "offset": i * 256,
                        "limit": 256,
                        "max_description_input_length": max_description_input_length,
                        "document_id": document_id,
                        "logger": logger,
                    }
                ),
                state=None,
                run_manager=self.run_manager,
            )

            all_results.append(await _collect_results(node_descriptions))

            logger.info(
                f"KGService: Completed kg_entity_description for batch {i+1}/{num_batches} for document {document_id}"
            )

        await self.providers.database.set_workflow_status(
            id=document_id,
            status_type="kg_extraction_status",
            status=KGExtractionStatus.SUCCESS,
        )

        logger.info(
            f"KGService: Completed kg_entity_description for document {document_id} in {time.time() - start_time:.2f} seconds",
        )

        return all_results

    @telemetry_event("get_graph_status")
    async def get_graph_status(
        self,
        collection_id: UUID,
        **kwargs,
    ):
        raise NotImplementedError("Not implemented")

    @telemetry_event("kg_clustering")
    async def kg_clustering(
        self,
        collection_id: UUID,
        graph_id: UUID,
        generation_config: GenerationConfig,
        leiden_params: dict,
        **kwargs,
    ):

        logger.info(
            f"Running ClusteringPipe for collection {collection_id} with settings {leiden_params}"
        )

        clustering_result = await self.pipes.kg_clustering_pipe.run(
            input=self.pipes.kg_clustering_pipe.Input(
                message={
                    "collection_id": collection_id,
                    "graph_id": graph_id,
                    "generation_config": generation_config,
                    "leiden_params": leiden_params,
                    "logger": logger,
                }
            ),
            state=None,
            run_manager=self.run_manager,
        )
        return await _collect_results(clustering_result)

    @telemetry_event("kg_community_summary")
    async def kg_community_summary(
        self,
        offset: int,
        limit: int,
        max_summary_input_length: int,
        generation_config: GenerationConfig,
        collection_id: UUID | None,
        graph_id: UUID | None,
        **kwargs,
    ):
        summary_results = await self.pipes.kg_community_summary_pipe.run(
            input=self.pipes.kg_community_summary_pipe.Input(
                message={
                    "offset": offset,
                    "limit": limit,
                    "generation_config": generation_config,
                    "max_summary_input_length": max_summary_input_length,
                    "collection_id": collection_id,
                    "graph_id": graph_id,
                    "logger": logger,
                }
            ),
            state=None,
            run_manager=self.run_manager,
        )
        return await _collect_results(summary_results)

    @telemetry_event("delete_graph_for_documents")
    async def delete_graph_for_documents(
        self,
        document_ids: list[UUID],
        **kwargs,
    ):
        # TODO: Implement this, as it needs some checks.
        raise NotImplementedError

    @telemetry_event("delete_graph")
    async def delete_graph(
        self,
        collection_id: UUID,
        cascade: bool,
        **kwargs,
    ):
        return await self.delete_graph_for_collection(
            collection_id=collection_id, cascade=cascade
        )

    @telemetry_event("delete_graph_for_collection")
    async def delete_graph_for_collection(
        self,
        collection_id: UUID,
        cascade: bool,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.delete_graph_for_collection(
            collection_id=collection_id,
            cascade=cascade,
        )

    @telemetry_event("delete_node_via_document_id")
    async def delete_node_via_document_id(
        self,
        document_id: UUID,
        collection_id: UUID,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.delete_node_via_document_id(
            document_id=document_id,
            collection_id=collection_id,
        )

    @telemetry_event("get_creation_estimate")
    async def get_creation_estimate(
        self,
        kg_creation_settings: KGCreationSettings,
        document_id: Optional[UUID] = None,
        collection_id: Optional[UUID] = None,
        **kwargs,
    ):
        return (
            await self.providers.database.graph_handler.get_creation_estimate(
                document_id=document_id,
                collection_id=collection_id,
                kg_creation_settings=kg_creation_settings,
            )
        )

    @telemetry_event("get_enrichment_estimate")
    async def get_enrichment_estimate(
        self,
        collection_id: Optional[UUID] = None,
        graph_id: Optional[UUID] = None,
        kg_enrichment_settings: KGEnrichmentSettings = KGEnrichmentSettings(),
        **kwargs,
    ):

        if graph_id is None and collection_id is None:
            raise ValueError(
                "Either graph_id or collection_id must be provided"
            )

        return await self.providers.database.graph_handler.get_enrichment_estimate(
            collection_id=collection_id,
            graph_id=graph_id,
            kg_enrichment_settings=kg_enrichment_settings,
        )

    @telemetry_event("get_deduplication_estimate")
    async def get_deduplication_estimate(
        self,
        collection_id: UUID,
        kg_deduplication_settings: KGEntityDeduplicationSettings,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.get_deduplication_estimate(
            collection_id=collection_id,
            kg_deduplication_settings=kg_deduplication_settings,
        )

    @telemetry_event("kg_entity_deduplication")
    async def kg_entity_deduplication(
        self,
        collection_id: UUID,
        graph_id: UUID,
        kg_entity_deduplication_type: KGEntityDeduplicationType,
        kg_entity_deduplication_prompt: str,
        generation_config: GenerationConfig,
        **kwargs,
    ):
        deduplication_results = await self.pipes.kg_entity_deduplication_pipe.run(
            input=self.pipes.kg_entity_deduplication_pipe.Input(
                message={
                    "collection_id": collection_id,
                    "graph_id": graph_id,
                    "kg_entity_deduplication_type": kg_entity_deduplication_type,
                    "kg_entity_deduplication_prompt": kg_entity_deduplication_prompt,
                    "generation_config": generation_config,
                    **kwargs,
                }
            ),
            state=None,
            run_manager=self.run_manager,
        )
        return await _collect_results(deduplication_results)

    @telemetry_event("kg_entity_deduplication_summary")
    async def kg_entity_deduplication_summary(
        self,
        collection_id: UUID,
        offset: int,
        limit: int,
        kg_entity_deduplication_type: KGEntityDeduplicationType,
        kg_entity_deduplication_prompt: str,
        generation_config: GenerationConfig,
        **kwargs,
    ):

        logger.info(
            f"Running kg_entity_deduplication_summary for collection {collection_id} with settings {kwargs}"
        )
        deduplication_summary_results = await self.pipes.kg_entity_deduplication_summary_pipe.run(
            input=self.pipes.kg_entity_deduplication_summary_pipe.Input(
                message={
                    "collection_id": collection_id,
                    "offset": offset,
                    "limit": limit,
                    "kg_entity_deduplication_type": kg_entity_deduplication_type,
                    "kg_entity_deduplication_prompt": kg_entity_deduplication_prompt,
                    "generation_config": generation_config,
                }
            ),
            state=None,
            run_manager=self.run_manager,
        )

        return await _collect_results(deduplication_summary_results)

    @telemetry_event("tune_prompt")
    async def tune_prompt(
        self,
        prompt_name: str,
        collection_id: UUID,
        documents_offset: int = 0,
        documents_limit: int = 100,
        chunks_offset: int = 0,
        chunks_limit: int = 100,
        **kwargs,
    ):

        document_response = (
            await self.providers.database.documents_in_collection(
                collection_id, offset=documents_offset, limit=documents_limit
            )
        )
        results = document_response["results"]

        if isinstance(results, int):
            raise TypeError("Expected list of documents, got count instead")

        documents = results

        if not documents:
            raise R2RException(
                message="No documents found in collection",
                status_code=404,
            )

        all_chunks = []

        for document in documents:
            chunks_response = (
                await self.providers.database.list_document_chunks(
                    document.id,
                    offset=chunks_offset,
                    limit=chunks_limit,
                )
            )

            if chunks := chunks_response.get("results", []):
                all_chunks.extend(chunks)
            else:
                logger.warning(f"No chunks found for document {document.id}")

        if not all_chunks:
            raise R2RException(
                message="No chunks found in documents",
                status_code=404,
            )

        chunk_texts = [
            chunk["text"] for chunk in all_chunks if chunk.get("text")
        ]

        # Pass chunks to the tuning pipe
        tune_prompt_results = await self.pipes.kg_prompt_tuning_pipe.run(
            input=self.pipes.kg_prompt_tuning_pipe.Input(
                message={
                    "collection_id": collection_id,
                    "prompt_name": prompt_name,
                    "chunks": chunk_texts,  # Pass just the text content
                    **kwargs,
                }
            ),
            state=None,
            run_manager=self.run_manager,
        )

        results = []
        async for result in tune_prompt_results:
            results.append(result)

        if not results:
            raise HTTPException(
                status_code=500,
                detail="No results generated from prompt tuning",
            )

        return results[0]
