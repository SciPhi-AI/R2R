import asyncio
import json
import logging
import math
import re
import time
from typing import Any, AsyncGenerator, Optional, Union
from uuid import UUID

from fastapi import HTTPException

from core.base import (
    DocumentChunk,
    KGExtraction,
    KGExtractionStatus,
    R2RDocumentProcessingError,
    RunManager,
)
from core.base.abstractions import (
    Community,
    Entity,
    GenerationConfig,
    Graph,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEnrichmentStatus,
    KGEntityDeduplicationSettings,
    KGEntityDeduplicationType,
    R2RException,
    Relationship,
)
from core.base.api.models import GraphResponse
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider
from core.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger()


MIN_VALID_KG_EXTRACTION_RESPONSE_LENGTH = 128


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
        **kwargs,
    ):
        try:

            logger.info(
                f"KGService: Processing document {document_id} for KG extraction"
            )

            await self.providers.database.set_workflow_status(
                id=document_id,
                status_type="extraction_status",
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
                status_type="extraction_status",
                status=KGExtractionStatus.FAILED,
            )
            raise e

        return await _collect_results(result_gen)

    @telemetry_event("create_entity")
    async def create_entity(
        self,
        name: str,
        description: str,
        parent_id: UUID,
        category: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Entity:

        description_embedding = str(
            await self.providers.embedding.async_get_embedding(description)
        )

        return await self.providers.database.graph_handler.entities.create(
            name=name,
            parent_id=parent_id,
            store_type="graphs",  # type: ignore
            category=category,
            description=description,
            description_embedding=description_embedding,
            metadata=metadata,
        )

    @telemetry_event("update_entity")
    async def update_entity(
        self,
        entity_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Entity:

        description_embedding = None
        if description is not None:
            description_embedding = str(
                await self.providers.embedding.async_get_embedding(description)
            )

        return await self.providers.database.graph_handler.entities.update(
            entity_id=entity_id,
            store_type="graphs",  # type: ignore
            name=name,
            description=description,
            description_embedding=description_embedding,
            category=category,
            metadata=metadata,
        )

    @telemetry_event("delete_entity")
    async def delete_entity(
        self,
        parent_id: UUID,
        entity_id: UUID,
    ):
        return await self.providers.database.graph_handler.entities.delete(
            parent_id=parent_id,
            entity_ids=[entity_id],
            store_type="graphs",  # type: ignore
        )

    @telemetry_event("get_entities")
    async def get_entities(
        self,
        parent_id: UUID,
        offset: int,
        limit: int,
        entity_ids: Optional[list[UUID]] = None,
        entity_names: Optional[list[str]] = None,
        include_embeddings: bool = False,
    ):
        return await self.providers.database.graph_handler.get_entities(
            parent_id=parent_id,
            offset=offset,
            limit=limit,
            entity_ids=entity_ids,
            entity_names=entity_names,
            include_embeddings=include_embeddings,
        )

    @telemetry_event("create_relationship")
    async def create_relationship(
        self,
        subject: str,
        subject_id: UUID,
        predicate: str,
        object: str,
        object_id: UUID,
        parent_id: UUID,
        description: str | None = None,
        weight: float | None = 1.0,
        metadata: Optional[dict[str, Any] | str] = None,
    ) -> Relationship:
        description_embedding = None
        if description:
            description_embedding = str(
                await self.providers.embedding.async_get_embedding(description)
            )

        return (
            await self.providers.database.graph_handler.relationships.create(
                subject=subject,
                subject_id=subject_id,
                predicate=predicate,
                object=object,
                object_id=object_id,
                parent_id=parent_id,
                description=description,
                description_embedding=description_embedding,
                weight=weight,
                metadata=metadata,
                store_type="graphs",  # type: ignore
            )
        )

    @telemetry_event("delete_relationship")
    async def delete_relationship(
        self,
        parent_id: UUID,
        relationship_id: UUID,
    ):
        return (
            await self.providers.database.graph_handler.relationships.delete(
                parent_id=parent_id,
                relationship_ids=[relationship_id],
                store_type="graphs",  # type: ignore
            )
        )

    @telemetry_event("update_relationship")
    async def update_relationship(
        self,
        relationship_id: UUID,
        subject: Optional[str] = None,
        subject_id: Optional[UUID] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        object_id: Optional[UUID] = None,
        description: Optional[str] = None,
        weight: Optional[float] = None,
        metadata: Optional[dict[str, Any] | str] = None,
    ) -> Relationship:

        description_embedding = None
        if description is not None:
            description_embedding = str(
                await self.providers.embedding.async_get_embedding(description)
            )

        return (
            await self.providers.database.graph_handler.relationships.update(
                relationship_id=relationship_id,
                subject=subject,
                subject_id=subject_id,
                predicate=predicate,
                object=object,
                object_id=object_id,
                description=description,
                description_embedding=description_embedding,
                weight=weight,
                metadata=metadata,
                store_type="graphs",  # type: ignore
            )
        )

    @telemetry_event("get_relationships")
    async def get_relationships(
        self,
        parent_id: UUID,
        offset: int,
        limit: int,
        relationship_ids: Optional[list[UUID]] = None,
        entity_names: Optional[list[str]] = None,
    ):
        return await self.providers.database.graph_handler.relationships.get(
            parent_id=parent_id,
            store_type="graphs",  # type: ignore
            offset=offset,
            limit=limit,
            relationship_ids=relationship_ids,
            entity_names=entity_names,
        )

    @telemetry_event("create_community")
    async def create_community(
        self,
        parent_id: UUID,
        name: str,
        summary: str,
        findings: Optional[list[str]],
        rating: Optional[float],
        rating_explanation: Optional[str],
    ) -> Community:
        description_embedding = str(
            await self.providers.embedding.async_get_embedding(summary)
        )
        return await self.providers.database.graph_handler.communities.create(
            parent_id=parent_id,
            store_type="graphs",  # type: ignore
            name=name,
            summary=summary,
            description_embedding=description_embedding,
            findings=findings,
            rating=rating,
            rating_explanation=rating_explanation,
        )

    @telemetry_event("update_community")
    async def update_community(
        self,
        community_id: UUID,
        name: Optional[str],
        summary: Optional[str],
        findings: Optional[list[str]],
        rating: Optional[float],
        rating_explanation: Optional[str],
    ) -> Community:
        summary_embedding = None
        if summary is not None:
            summary_embedding = str(
                await self.providers.embedding.async_get_embedding(summary)
            )

        return await self.providers.database.graph_handler.communities.update(
            community_id=community_id,
            store_type="graphs",  # type: ignore
            name=name,
            summary=summary,
            summary_embedding=summary_embedding,
            findings=findings,
            rating=rating,
            rating_explanation=rating_explanation,
        )

    @telemetry_event("delete_community")
    async def delete_community(
        self,
        parent_id: UUID,
        community_id: UUID,
    ) -> None:
        await self.providers.database.graph_handler.communities.delete(
            parent_id=parent_id,
            community_id=community_id,
        )

    @telemetry_event("list_communities")
    async def list_communities(
        self,
        collection_id: UUID,
        offset: int,
        limit: int,
    ):
        return await self.providers.database.graph_handler.communities.get(
            parent_id=collection_id,
            store_type="graphs",  # type: ignore
            offset=offset,
            limit=limit,
        )

    @telemetry_event("get_communities")
    async def get_communities(
        self,
        parent_id: UUID,
        offset: int,
        limit: int,
        community_ids: Optional[list[UUID]] = None,
        community_names: Optional[list[str]] = None,
        include_embeddings: bool = False,
    ):
        return await self.providers.database.graph_handler.get_communities(
            parent_id=parent_id,
            offset=offset,
            limit=limit,
            community_ids=community_ids,
            include_embeddings=include_embeddings,
        )

    # @telemetry_event("create_new_graph")
    # async def create_new_graph(
    #     self,
    #     collection_id: UUID,
    #     user_id: UUID,
    #     name: Optional[str],
    #     description: str = "",
    # ) -> GraphResponse:
    #     return await self.providers.database.graph_handler.create(
    #         collection_id=collection_id,
    #         user_id=user_id,
    #         name=name,
    #         description=description,
    #         graph_id=collection_id,
    #     )

    async def list_graphs(
        self,
        offset: int,
        limit: int,
        # user_ids: Optional[list[UUID]] = None,
        graph_ids: Optional[list[UUID]] = None,
        collection_id: Optional[UUID] = None,
    ) -> dict[str, list[GraphResponse] | int]:
        return await self.providers.database.graph_handler.list_graphs(
            offset=offset,
            limit=limit,
            # filter_user_ids=user_ids,
            filter_graph_ids=graph_ids,
            filter_collection_id=collection_id,
        )

    @telemetry_event("update_graph")
    async def update_graph(
        self,
        collection_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> GraphResponse:
        return await self.providers.database.graph_handler.update(
            collection_id=collection_id,
            name=name,
            description=description,
        )

    @telemetry_event("reset_graph_v3")
    async def reset_graph_v3(self, id: UUID) -> bool:
        await self.providers.database.graph_handler.reset(
            parent_id=id,
        )
        await self.providers.database.document_handler.set_workflow_status(
            id=id,
            status_type="graph_cluster_status",
            status=KGEnrichmentStatus.PENDING,
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
            status_type="extraction_status",
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
                entity_table_name="documents_entities",
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
            status_type="extraction_status",
            status=KGExtractionStatus.SUCCESS,
        )

        logger.info(
            f"KGService: Completed kg_entity_description for document {document_id} in {time.time() - start_time:.2f} seconds",
        )

        return all_results

    @telemetry_event("kg_clustering")
    async def kg_clustering(
        self,
        collection_id: UUID,
        # graph_id: UUID,
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
        # graph_id: UUID | None,
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
                    # "graph_id": graph_id,
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
        graph_creation_settings: KGCreationSettings,
        document_id: Optional[UUID] = None,
        collection_id: Optional[UUID] = None,
        **kwargs,
    ):
        return (
            await self.providers.database.graph_handler.get_creation_estimate(
                document_id=document_id,
                collection_id=collection_id,
                graph_creation_settings=graph_creation_settings,
            )
        )

    @telemetry_event("get_enrichment_estimate")
    async def get_enrichment_estimate(
        self,
        collection_id: Optional[UUID] = None,
        graph_id: Optional[UUID] = None,
        graph_enrichment_settings: KGEnrichmentSettings = KGEnrichmentSettings(),
        **kwargs,
    ):

        if graph_id is None and collection_id is None:
            raise ValueError(
                "Either graph_id or collection_id must be provided"
            )

        return await self.providers.database.graph_handler.get_enrichment_estimate(
            collection_id=collection_id,
            graph_id=graph_id,
            graph_enrichment_settings=graph_enrichment_settings,
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
        graph_entity_deduplication_type: KGEntityDeduplicationType,
        graph_entity_deduplication_prompt: str,
        generation_config: GenerationConfig,
        **kwargs,
    ):
        deduplication_results = await self.pipes.kg_entity_deduplication_pipe.run(
            input=self.pipes.kg_entity_deduplication_pipe.Input(
                message={
                    "collection_id": collection_id,
                    "graph_id": graph_id,
                    "graph_entity_deduplication_type": graph_entity_deduplication_type,
                    "graph_entity_deduplication_prompt": graph_entity_deduplication_prompt,
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
        graph_entity_deduplication_type: KGEntityDeduplicationType,
        graph_entity_deduplication_prompt: str,
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
                    "graph_entity_deduplication_type": graph_entity_deduplication_type,
                    "graph_entity_deduplication_prompt": graph_entity_deduplication_prompt,
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

    async def kg_extraction(  # type: ignore
        self,
        document_id: UUID,
        generation_config: GenerationConfig,
        max_knowledge_relationships: int,
        entity_types: list[str],
        relation_types: list[str],
        chunk_merge_count: int,
        filter_out_existing_chunks: bool = True,
        total_tasks: Optional[int] = None,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[KGExtraction, R2RDocumentProcessingError], None]:
        start_time = time.time()

        logger.info(
            f"KGExtractionPipe: Processing document {document_id} for KG extraction",
        )

        # Then create the extractions from the results
        limit = 100
        offset = 0
        chunks = []
        while True:
            chunk_req = await self.providers.database.list_document_chunks(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
                document_id=document_id,
                offset=offset,
                limit=limit,
            )

            chunks.extend(
                [
                    DocumentChunk(
                        id=chunk["id"],
                        document_id=chunk["document_id"],
                        owner_id=chunk["owner_id"],
                        collection_ids=chunk["collection_ids"],
                        data=chunk["text"],
                        metadata=chunk["metadata"],
                    )
                    for chunk in chunk_req["results"]
                ]
            )
            if len(chunk_req["results"]) < limit:
                break
            offset += limit

        logger.info(f"Found {len(chunks)} chunks for document {document_id}")
        if len(chunks) == 0:
            logger.info(f"No chunks found for document {document_id}")
            raise R2RException(
                message="No chunks found for document",
                status_code=404,
            )

        if filter_out_existing_chunks:
            existing_chunk_ids = await self.providers.database.graph_handler.get_existing_document_entity_chunk_ids(
                document_id=document_id
            )
            chunks = [
                chunk for chunk in chunks if chunk.id not in existing_chunk_ids
            ]
            logger.info(
                f"Filtered out {len(existing_chunk_ids)} existing chunks, remaining {len(chunks)} chunks for document {document_id}"
            )

            if len(chunks) == 0:
                logger.info(f"No extractions left for document {document_id}")
                return

        logger.info(
            f"KGExtractionPipe: Obtained {len(chunks)} chunks to process, time from start: {time.time() - start_time:.2f} seconds",
        )

        # sort the extractions accroding to chunk_order field in metadata in ascending order
        chunks = sorted(
            chunks,
            key=lambda x: x.metadata.get("chunk_order", float("inf")),
        )

        # group these extractions into groups of chunk_merge_count
        grouped_chunks = [
            chunks[i : i + chunk_merge_count]
            for i in range(0, len(chunks), chunk_merge_count)
        ]

        logger.info(
            f"KGExtractionPipe: Extracting KG Relationships for document and created {len(grouped_chunks)} tasks, time from start: {time.time() - start_time:.2f} seconds",
        )

        tasks = [
            asyncio.create_task(
                self._extract_kg(
                    chunks=chunk_group,
                    generation_config=generation_config,
                    max_knowledge_relationships=max_knowledge_relationships,
                    entity_types=entity_types,
                    relation_types=relation_types,
                    task_id=task_id,
                    total_tasks=len(grouped_chunks),
                )
            )
            for task_id, chunk_group in enumerate(grouped_chunks)
        ]

        completed_tasks = 0
        total_tasks = len(tasks)

        logger.info(
            f"KGExtractionPipe: Waiting for {total_tasks} KG extraction tasks to complete",
        )

        for completed_task in asyncio.as_completed(tasks):
            try:
                yield await completed_task
                completed_tasks += 1
                if completed_tasks % 100 == 0:
                    logger.info(
                        f"KGExtractionPipe: Completed {completed_tasks}/{total_tasks} KG extraction tasks",
                    )
            except Exception as e:
                logger.error(f"Error in Extracting KG Relationships: {e}")
                yield R2RDocumentProcessingError(
                    document_id=document_id,
                    error_message=str(e),
                )

        logger.info(
            f"KGExtractionPipe: Completed {completed_tasks}/{total_tasks} KG extraction tasks, time from start: {time.time() - start_time:.2f} seconds",
        )

    async def _extract_kg(
        self,
        chunks: list[DocumentChunk],
        generation_config: GenerationConfig,
        max_knowledge_relationships: int,
        entity_types: list[str],
        relation_types: list[str],
        retries: int = 5,
        delay: int = 2,
        task_id: Optional[int] = None,
        total_tasks: Optional[int] = None,
    ) -> KGExtraction:
        """
        Extracts NER relationships from a extraction with retries.
        """

        # combine all extractions into a single string
        combined_extraction: str = " ".join([chunk.data for chunk in chunks])  # type: ignore

        messages = await self.providers.database.prompt_handler.get_message_payload(
            task_prompt_name=self.providers.database.config.graph_creation_settings.graphrag_relationships_extraction_few_shot,
            task_inputs={
                "input": combined_extraction,
                "max_knowledge_relationships": max_knowledge_relationships,
                "entity_types": "\n".join(entity_types),
                "relation_types": "\n".join(relation_types),
            },
        )

        for attempt in range(retries):
            try:
                response = await self.providers.llm.aget_completion(
                    messages,
                    generation_config=generation_config,
                )

                kg_extraction = response.choices[0].message.content

                if not kg_extraction:
                    raise R2RException(
                        "No knowledge graph extraction found in the response string, the selected LLM likely failed to format it's response correctly.",
                        400,
                    )

                entity_pattern = (
                    r'\("entity"\${4}([^$]+)\${4}([^$]+)\${4}([^$]+)\)'
                )
                relationship_pattern = r'\("relationship"\${4}([^$]+)\${4}([^$]+)\${4}([^$]+)\${4}([^$]+)\${4}(\d+(?:\.\d+)?)\)'

                async def parse_fn(response_str: str) -> Any:
                    entities = re.findall(entity_pattern, response_str)

                    if (
                        len(kg_extraction)
                        > MIN_VALID_KG_EXTRACTION_RESPONSE_LENGTH
                        and len(entities) == 0
                    ):
                        raise R2RException(
                            f"No entities found in the response string, the selected LLM likely failed to format it's response correctly. {response_str}",
                            400,
                        )

                    relationships = re.findall(
                        relationship_pattern, response_str
                    )

                    entities_arr = []
                    for entity in entities:
                        entity_value = entity[0]
                        entity_category = entity[1]
                        entity_description = entity[2]
                        description_embedding = (
                            await self.providers.embedding.async_get_embedding(
                                entity_description
                            )
                        )
                        entities_arr.append(
                            Entity(
                                category=entity_category,
                                description=entity_description,
                                name=entity_value,
                                parent_id=chunks[0].document_id,
                                chunk_ids=[chunk.id for chunk in chunks],
                                description_embedding=description_embedding,
                                attributes={},
                            )
                        )

                    relations_arr = []
                    for relationship in relationships:
                        subject = relationship[0]
                        object = relationship[1]
                        predicate = relationship[2]
                        description = relationship[3]
                        weight = float(relationship[4])
                        relationship_embedding = (
                            await self.providers.embedding.async_get_embedding(
                                description
                            )
                        )

                        # check if subject and object are in entities_dict
                        relations_arr.append(
                            Relationship(
                                subject=subject,
                                predicate=predicate,
                                object=object,
                                description=description,
                                weight=weight,
                                parent_id=chunks[0].document_id,
                                chunk_ids=[chunk.id for chunk in chunks],
                                attributes={},
                                description_embedding=relationship_embedding,
                            )
                        )

                    return entities_arr, relations_arr

                entities, relationships = await parse_fn(kg_extraction)
                return KGExtraction(
                    entities=entities,
                    relationships=relationships,
                )

            except (
                Exception,
                json.JSONDecodeError,
                KeyError,
                IndexError,
                R2RException,
            ) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    print(
                        f"Failed after retries with for chunk {chunks[0].id} of document {chunks[0].document_id}: {e}"
                    )

        print(
            f"KGExtractionPipe: Completed task number {task_id} of {total_tasks} for document {chunks[0].document_id}",
        )

        return KGExtraction(
            entities=[],
            relationships=[],
        )

    async def store_kg_extractions(
        self,
        kg_extractions: list[KGExtraction],
    ):
        """
        Stores a batch of knowledge graph extractions in the graph database.
        """

        for extraction in kg_extractions:
            entities_id_map = {}
            for entity in extraction.entities:
                result = await self.providers.database.graph_handler.entities.create(
                    name=entity.name,
                    parent_id=entity.parent_id,
                    store_type="documents",  # type: ignore
                    category=entity.category,
                    description=entity.description,
                    description_embedding=entity.description_embedding,
                    chunk_ids=entity.chunk_ids,
                    metadata=entity.metadata,
                )
                entities_id_map[entity.name] = result.id

            if extraction.relationships:

                for relationship in extraction.relationships:
                    await self.providers.database.graph_handler.relationships.create(
                        subject=relationship.subject,
                        subject_id=entities_id_map.get(
                            relationship.subject, None
                        ),
                        predicate=relationship.predicate,
                        object=relationship.object,
                        object_id=entities_id_map.get(
                            relationship.object, None
                        ),
                        parent_id=relationship.parent_id,
                        description=relationship.description,
                        description_embedding=relationship.description_embedding,
                        weight=relationship.weight,
                        metadata=relationship.metadata,
                        store_type="documents",  # type: ignore
                    )
