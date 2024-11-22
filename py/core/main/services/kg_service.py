import logging
import math
import time
from typing import Any, AsyncGenerator, Optional
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
from core.base.api.models import GraphResponse
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
        chunk_merge_count: int,
        max_knowledge_relationships: int,
        entity_types: list[str],
        relation_types: list[str],
        auth_user: Optional[Any] = None,
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
                        "chunk_merge_count": chunk_merge_count,
                        "max_knowledge_relationships": max_knowledge_relationships,
                        "entity_types": entity_types,
                        "relation_types": relation_types,
                        "logger": logger,
                        "auth_user": auth_user,
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
        name: str,
        description: str,
        category: Optional[str] = None,
        user_id: Optional[UUID] = None,
        attributes: Optional[dict] = None,
    ) -> Entity:

        description_embedding = str(
            await self.providers.embedding.async_get_embedding(description)
        )

        return await self.providers.database.graph_handler.entities.create(
            name=name,
            category=category,
            description=description,
            description_embedding=description_embedding,
            attributes=attributes,
            user_id=user_id,
        )

    async def list_entities(
        self,
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
        entity_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[Entity] | int]:
        return (
            await self.providers.database.graph_handler.entities.list_entities(
                offset=offset,
                limit=limit,
                filter_user_ids=user_ids,
                filter_entity_ids=entity_ids,
            )
        )

    @telemetry_event("update_entity")
    async def update_entity(
        self,
        entity_id: UUID,
        name: Optional[str],
        category: Optional[str],
        description: Optional[str],
        attributes: Optional[dict],
        user_id: UUID,
    ):

        if description is not None:
            description_embedding = str(
                await self.providers.embedding.async_get_embedding(description)
            )
        else:
            description_embedding = None

        return await self.providers.database.graph_handler.entities.update(
            entity_id=entity_id,
            name=name,
            category=category,
            description=description,
            description_embedding=description_embedding,
            attributes=attributes,
            user_id=user_id,
        )

    @telemetry_event("delete_entity")
    async def delete_entity_v3(self, id: UUID) -> bool:
        await self.providers.database.graph_handler.entities.delete(
            entity_id=id,
        )
        return True

    @telemetry_event("add_entity_to_graph")
    async def add_entity_to_graph(
        self,
        graph_id: UUID,
        entity_id: UUID,
    ):
        await self.providers.database.graph_handler.entities.add_to_graph(
            graph_id=graph_id,
            entity_id=entity_id,
        )

        return {"message": "Entity assigned to graph successfully"}

    @telemetry_event("remove_entity_from_graph")
    async def remove_entity_from_graph(
        self,
        graph_id: UUID,
        entity_id: UUID,
    ) -> None:
        await self.providers.database.graph_handler.entities.remove_from_graph(
            graph_id=graph_id,
            entity_id=entity_id,
        )

    # TODO: deprecate this
    @telemetry_event("get_entities")
    async def get_entities(
        self,
        collection_id: Optional[UUID] = None,
        entity_ids: Optional[list[str]] = None,
        entity_table_name: str = "entity",
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
        filter_user_ids: Optional[list[UUID]] = None,
        filter_relationship_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = 100,
    ):
        return await self.providers.database.graph_handler.relationships.list_relationships(
            filter_user_ids=filter_user_ids,
            filter_relationship_ids=filter_relationship_ids,
            offset=offset,
            limit=limit,
        )

    @telemetry_event("create_relationships_v3")
    async def create_relationships_v3(
        self,
        subject: str,
        predicate: str,
        object: str,
        description: str,
        weight: Optional[float],
        attributes: Optional[dict],
        user_id: UUID,
        **kwargs,
    ):
        return (
            await self.providers.database.graph_handler.relationships.create(
                subject=subject,
                predicate=predicate,
                object=object,
                description=description,
                weight=weight,
                attributes=attributes,
                user_id=user_id,
            )
        )

    @telemetry_event("delete_relationship_v3")
    async def delete_relationship_v3(
        self,
        id: UUID,
        **kwargs,
    ):
        return (
            await self.providers.database.graph_handler.relationships.delete(
                id=id,
            )
        )

    @telemetry_event("update_relationship_v3")
    async def update_relationship_v3(
        self,
        relationship_id: UUID,
        subject: str,
        predicate: str,
        object: str,
        description: str,
        weight: Optional[float],
        attributes: Optional[dict],
        user_id: UUID,
        **kwargs,
    ):
        return (
            await self.providers.database.graph_handler.relationships.update(
                relationship_id=relationship_id,
                subject=subject,
                predicate=predicate,
                object=object,
                description=description,
                weight=weight,
                attributes=attributes,
                user_id=user_id,
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

    @telemetry_event("add_relationship_to_graph")
    async def add_relationship_to_graph(
        self,
        graph_id: UUID,
        relationship_id: UUID,
    ) -> dict[str, str]:

        await self.providers.database.graph_handler.relationships.add_to_graph(
            graph_id=graph_id, relationship_id=relationship_id
        )

        return {"message": "Relationship added to graph successfully"}

    @telemetry_event("remove_relationship_from_graph")
    async def remove_relationship_from_graph(
        self,
        graph_id: UUID,
        relationship_id: UUID,
    ):
        return await self.providers.database.graph_handler.relationships.remove_from_graph(
            graph_id=graph_id, relationship_id=relationship_id
        )

    ################### COMMUNITIES ###################

    @telemetry_event("create_community_v3")
    async def create_community_v3(
        self,
        graph_id: UUID,
        name: str,
        summary: str,
        findings: list[str],
        rating: Optional[float],
        rating_explanation: Optional[str],
        level: Optional[int],
        attributes: Optional[dict],
        user_id: UUID,
        **kwargs,
    ):
        embedding = str(
            await self.providers.embedding.async_get_embedding(summary)
        )
        return await self.providers.database.graph_handler.communities.create(
            graph_id=graph_id,
            name=name,
            summary=summary,
            embedding=embedding,
            findings=findings,
            rating=rating,
            rating_explanation=rating_explanation,
            level=level,
            attributes=attributes,
            user_id=user_id,
        )

    @telemetry_event("update_community_v3")
    async def update_community_v3(
        self,
        id: UUID,
        community_id: UUID,
        name: Optional[str],
        summary: Optional[str],
        findings: Optional[list[str]],
        rating: Optional[float],
        rating_explanation: Optional[str],
        level: Optional[int],
        attributes: Optional[dict],
        user_id: UUID,
        **kwargs,
    ):
        if summary is not None:
            embedding = str(
                await self.providers.embedding.async_get_embedding(summary)
            )
        else:
            embedding = None

        return await self.providers.database.graph_handler.communities.update(
            id=id,
            community_id=community_id,
            name=name,
            summary=summary,
            embedding=embedding,
            findings=findings,
            rating=rating,
            rating_explanation=rating_explanation,
            level=level,
            attributes=attributes,
            user_id=user_id,
        )

    @telemetry_event("delete_community_v3")
    async def delete_community_v3(
        self,
        graph_id: UUID,
        community_id: UUID,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.communities.delete(
            graph_id=graph_id,
            community_id=community_id,
        )

    @telemetry_event("list_communities_v3")
    async def list_communities_v3(
        self,
        graph_id: UUID,
        offset: int,
        limit: int,
        filter_community_ids: Optional[list[UUID]] = None,
        filter_user_ids: Optional[list[UUID]] = None,
        **kwargs,
    ):
        return await self.providers.database.graph_handler.communities.list_communities(
            graph_id=graph_id,
            offset=offset,
            limit=limit,
            filter_community_ids=filter_community_ids,
            filter_user_ids=filter_user_ids,
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

    @telemetry_event("create_new_graph")
    async def create_new_graph(
        self,
        user_id: UUID,
        name: Optional[str],
        description: str = "",
    ) -> GraphResponse:
        return await self.providers.database.graph_handler.create(
            user_id=user_id,
            name=name,
            description=description,
        )

    async def list_graphs(
        self,
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
        graph_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[GraphResponse] | int]:
        return await self.providers.database.graph_handler.list_graphs(
            offset=offset,
            limit=limit,
            filter_user_ids=user_ids,
            filter_graph_ids=graph_ids,
        )

    @telemetry_event("get_graphs")
    async def get_graphs(
        self, offset: int, limit: int, graph_id: Optional[UUID] = None
    ) -> Graph:
        return await self.providers.database.graph_handler.get(
            offset=offset, limit=limit, graph_id=graph_id
        )

    @telemetry_event("update_graph")
    async def update_graph(
        self,
        graph_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> GraphResponse:
        return await self.providers.database.graph_handler.update(
            graph_id=graph_id,
            name=name,
            description=description,
        )

    @telemetry_event("delete_graph_v3")
    async def delete_graph_v3(self, id: UUID) -> bool:
        await self.providers.database.graph_handler.delete(
            graph_id=id,
        )
        return True

    @telemetry_event("get_document_ids_for_create_graph")
    async def get_document_ids_for_create_graph(
        self,
        collection_id: UUID,
        force_kg_creation: bool = False,
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
        auth_user: Any,
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

        if entity_count == 0:
            raise R2RException(
                "No entities found for document. Please check the document for errors."
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
                        "auth_user": auth_user,
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

    async def add_documents_to_graph(
        self, graph_id: UUID, document_ids: list[UUID]
    ) -> dict:

        await self.providers.database.graph_handler.add_documents_to_graph(
            graph_id=graph_id,
            document_ids=document_ids,
        )

        return {
            "message": "All entities and relationships from the documents have been added to the graph."
        }

    async def remove_documents_from_graph(
        self, graph_id: UUID, document_ids: list[UUID]
    ) -> None:

        await self.providers.database.graph_handler.remove_documents_from_graph(
            graph_id=graph_id,
            document_ids=document_ids,
        )

    async def add_collection_to_graph(
        self, graph_id: UUID, collection_id: UUID
    ) -> dict:
        await self.providers.database.graph_handler.add_collection_to_graph(
            graph_id=graph_id,
            collection_id=collection_id,
        )

        return {
            "message": "All entities and relationships from the collection have been added to the graph."
        }

    async def remove_collection_from_graph(
        self, graph_id: UUID, collection_id: UUID
    ) -> None:

        await self.providers.database.graph_handler.remove_collection_from_graph(
            graph_id=graph_id,
            collection_id=collection_id,
        )
