import asyncio
import json
import logging
import math
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

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
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEnrichmentStatus,
    R2RException,
    Relationship,
    StoreType,
)
from core.base.api.models import GraphResponse
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


# TODO - Fix naming convention to read `KGService` instead of `GraphService`
# this will require a minor change in how services are registered.
class GraphService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipes: R2RPipes,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
    ):
        super().__init__(
            config,
            providers,
            pipes,
            pipelines,
            agents,
            run_manager,
        )

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

        return await self.providers.database.graphs_handler.entities.create(
            name=name,
            parent_id=parent_id,
            store_type=StoreType.GRAPHS,
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

        return await self.providers.database.graphs_handler.entities.update(
            entity_id=entity_id,
            store_type=StoreType.GRAPHS,
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
        return await self.providers.database.graphs_handler.entities.delete(
            parent_id=parent_id,
            entity_ids=[entity_id],
            store_type=StoreType.GRAPHS,
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
        return await self.providers.database.graphs_handler.get_entities(
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
            await self.providers.database.graphs_handler.relationships.create(
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
                store_type=StoreType.GRAPHS,
            )
        )

    @telemetry_event("delete_relationship")
    async def delete_relationship(
        self,
        parent_id: UUID,
        relationship_id: UUID,
    ):
        return (
            await self.providers.database.graphs_handler.relationships.delete(
                parent_id=parent_id,
                relationship_ids=[relationship_id],
                store_type=StoreType.GRAPHS,
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
            await self.providers.database.graphs_handler.relationships.update(
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
                store_type=StoreType.GRAPHS,
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
        return await self.providers.database.graphs_handler.relationships.get(
            parent_id=parent_id,
            store_type=StoreType.GRAPHS,
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
        return await self.providers.database.graphs_handler.communities.create(
            parent_id=parent_id,
            store_type=StoreType.GRAPHS,
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

        return await self.providers.database.graphs_handler.communities.update(
            community_id=community_id,
            store_type=StoreType.GRAPHS,
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
        await self.providers.database.graphs_handler.communities.delete(
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
        return await self.providers.database.graphs_handler.communities.get(
            parent_id=collection_id,
            store_type=StoreType.GRAPHS,
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
        return await self.providers.database.graphs_handler.get_communities(
            parent_id=parent_id,
            offset=offset,
            limit=limit,
            community_ids=community_ids,
            include_embeddings=include_embeddings,
        )

    async def list_graphs(
        self,
        offset: int,
        limit: int,
        # user_ids: Optional[list[UUID]] = None,
        graph_ids: Optional[list[UUID]] = None,
        collection_id: Optional[UUID] = None,
    ) -> dict[str, list[GraphResponse] | int]:
        return await self.providers.database.graphs_handler.list_graphs(
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
        return await self.providers.database.graphs_handler.update(
            collection_id=collection_id,
            name=name,
            description=description,
        )

    @telemetry_event("reset_graph_v3")
    async def reset_graph_v3(self, id: UUID) -> bool:
        await self.providers.database.graphs_handler.reset(
            parent_id=id,
        )
        await self.providers.database.documents_handler.set_workflow_status(
            id=id,
            status_type="graph_cluster_status",
            status=KGEnrichmentStatus.PENDING,
        )
        return True

    @telemetry_event("get_document_ids_for_create_graph")
    async def get_document_ids_for_create_graph(
        self,
        collection_id: UUID,
        **kwargs,
    ):
        document_status_filter = [
            KGExtractionStatus.PENDING,
            KGExtractionStatus.FAILED,
        ]

        return await self.providers.database.documents_handler.get_document_ids_by_status(
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
            await self.providers.database.graphs_handler.get_entity_count(
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

            node_descriptions = await self.pipes.graph_description_pipe.run(
                input=self.pipes.graph_description_pipe.Input(
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

        await self.providers.database.documents_handler.set_workflow_status(
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

        clustering_result = await self.pipes.graph_clustering_pipe.run(
            input=self.pipes.graph_clustering_pipe.Input(
                message={
                    "collection_id": collection_id,
                    "generation_config": generation_config,
                    "leiden_params": leiden_params,
                    "logger": logger,
                    "clustering_mode": self.config.database.graph_creation_settings.clustering_mode,
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
        summary_results = await self.pipes.graph_community_summary_pipe.run(
            input=self.pipes.graph_community_summary_pipe.Input(
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
    ):
        return await self.delete(collection_id=collection_id)

    @telemetry_event("delete")
    async def delete(
        self,
        collection_id: UUID,
        **kwargs,
    ):
        return await self.providers.database.graphs_handler.delete(
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
            await self.providers.database.graphs_handler.get_creation_estimate(
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

        return await self.providers.database.graphs_handler.get_enrichment_estimate(
            collection_id=collection_id,
            graph_id=graph_id,
            graph_enrichment_settings=graph_enrichment_settings,
        )

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
    ) -> AsyncGenerator[KGExtraction | R2RDocumentProcessingError, None]:
        start_time = time.time()

        logger.info(
            f"Graph Extraction: Processing document {document_id} for KG extraction",
        )

        # Then create the extractions from the results
        limit = 100
        offset = 0
        chunks = []
        while True:
            chunk_req = await self.providers.database.chunks_handler.list_document_chunks(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
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
            existing_chunk_ids = await self.providers.database.graphs_handler.get_existing_document_entity_chunk_ids(
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
            f"Graph Extraction: Obtained {len(chunks)} chunks to process, time from start: {time.time() - start_time:.2f} seconds",
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
            f"Graph Extraction: Extracting KG Relationships for document and created {len(grouped_chunks)} tasks, time from start: {time.time() - start_time:.2f} seconds",
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
            f"Graph Extraction: Waiting for {total_tasks} KG extraction tasks to complete",
        )

        for completed_task in asyncio.as_completed(tasks):
            try:
                yield await completed_task
                completed_tasks += 1
                if completed_tasks % 100 == 0:
                    logger.info(
                        f"Graph Extraction: Completed {completed_tasks}/{total_tasks} KG extraction tasks",
                    )
            except Exception as e:
                logger.error(f"Error in Extracting KG Relationships: {e}")
                yield R2RDocumentProcessingError(
                    document_id=document_id,
                    error_message=str(e),
                )

        logger.info(
            f"Graph Extraction: Completed {completed_tasks}/{total_tasks} KG extraction tasks, time from start: {time.time() - start_time:.2f} seconds",
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

        response = await self.providers.database.documents_handler.get_documents_overview(  # type: ignore
            offset=0,
            limit=1,
            filter_document_ids=[chunks[0].document_id],
        )
        document_summary = (
            response["results"][0].summary if response["results"] else None
        )

        messages = await self.providers.database.prompts_handler.get_message_payload(
            task_prompt_name=self.providers.database.config.graph_creation_settings.graphrag_relationships_extraction_few_shot,
            task_inputs={
                "document_summary": document_summary,
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

                def sanitize_xml(response_str: str) -> str:
                    """Attempts to sanitize the XML response string by"""
                    # Strip any markdown
                    response_str = re.sub(r"```xml|```", "", response_str)

                    # Remove any XML processing instructions or style tags
                    response_str = re.sub(r"<\?.*?\?>", "", response_str)
                    response_str = re.sub(
                        r"<userStyle>.*?</userStyle>", "", response_str
                    )

                    # Only replace & if it's not already part of an escape sequence
                    response_str = re.sub(
                        r"&(?!amp;|quot;|apos;|lt;|gt;)", "&amp;", response_str
                    )

                    # Remove any root tags since we'll add them in parse_fn
                    response_str = response_str.replace("<root>", "").replace(
                        "</root>", ""
                    )

                    # Find and track all opening/closing tags
                    opened_tags = []
                    for match in re.finditer(
                        r"<(\w+)(?:\s+[^>]*)?>", response_str
                    ):
                        tag = match.group(1)
                        if tag != "root":  # Don't track root tag
                            opened_tags.append(tag)

                    for match in re.finditer(r"</(\w+)>", response_str):
                        tag = match.group(1)
                        if tag in opened_tags:
                            opened_tags.remove(tag)

                    # Close any unclosed tags
                    for tag in reversed(opened_tags):
                        response_str += f"</{tag}>"

                    return response_str.strip()

                async def parse_fn(response_str: str) -> Any:
                    # Wrap the response in a root element to ensure it is valid XML
                    cleaned_xml = sanitize_xml(response_str)
                    wrapped_xml = f"<root>{cleaned_xml}</root>"

                    try:
                        root = ET.fromstring(wrapped_xml)
                    except ET.ParseError as e:
                        raise R2RException(
                            f"Failed to parse XML response: {e}. Response: {wrapped_xml}",
                            400,
                        )

                    entities = root.findall(".//entity")
                    if (
                        len(kg_extraction)
                        > MIN_VALID_KG_EXTRACTION_RESPONSE_LENGTH
                        and len(entities) == 0
                    ):
                        raise R2RException(
                            f"No entities found in the response string, the selected LLM likely failed to format it's response correctly. {response_str}",
                            400,
                        )

                    entities_arr = []
                    for entity_elem in entities:
                        entity_value = entity_elem.get("name")
                        entity_category = entity_elem.find("type").text
                        entity_description = entity_elem.find(
                            "description"
                        ).text

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
                    for rel_elem in root.findall(".//relationship"):
                        if rel_elem is not None:
                            source_elem = rel_elem.find("source")
                            target_elem = rel_elem.find("target")
                            type_elem = rel_elem.find("type")
                            desc_elem = rel_elem.find("description")
                            weight_elem = rel_elem.find("weight")

                            if all(
                                [
                                    elem is not None
                                    for elem in [
                                        source_elem,
                                        target_elem,
                                        type_elem,
                                        desc_elem,
                                        weight_elem,
                                    ]
                                ]
                            ):
                                assert source_elem is not None
                                assert target_elem is not None
                                assert type_elem is not None
                                assert desc_elem is not None
                                assert weight_elem is not None

                                subject = source_elem.text
                                object = target_elem.text
                                predicate = type_elem.text
                                description = desc_elem.text
                                weight = float(weight_elem.text)

                                relationship_embedding = await self.providers.embedding.async_get_embedding(
                                    description
                                )

                                relations_arr.append(
                                    Relationship(
                                        subject=subject,
                                        predicate=predicate,
                                        object=object,
                                        description=description,
                                        weight=weight,
                                        parent_id=chunks[0].document_id,
                                        chunk_ids=[
                                            chunk.id for chunk in chunks
                                        ],
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
                    logger.warning(
                        f"Failed after retries with for chunk {chunks[0].id} of document {chunks[0].document_id}: {e}"
                    )

        logger.info(
            f"Graph Extraction: Completed task number {task_id} of {total_tasks} for document {chunks[0].document_id}",
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
                result = await self.providers.database.graphs_handler.entities.create(
                    name=entity.name,
                    parent_id=entity.parent_id,
                    store_type=StoreType.DOCUMENTS,
                    category=entity.category,
                    description=entity.description,
                    description_embedding=entity.description_embedding,
                    chunk_ids=entity.chunk_ids,
                    metadata=entity.metadata,
                )
                entities_id_map[entity.name] = result.id

            if extraction.relationships:
                for relationship in extraction.relationships:
                    await self.providers.database.graphs_handler.relationships.create(
                        subject=relationship.subject,
                        subject_id=entities_id_map.get(relationship.subject),
                        predicate=relationship.predicate,
                        object=relationship.object,
                        object_id=entities_id_map.get(relationship.object),
                        parent_id=relationship.parent_id,
                        description=relationship.description,
                        description_embedding=relationship.description_embedding,
                        weight=relationship.weight,
                        metadata=relationship.metadata,
                        store_type=StoreType.DOCUMENTS,
                    )

    @telemetry_event("deduplicate_document_entities")
    async def deduplicate_document_entities(
        self,
        document_id: UUID,
    ):
        """
        Deduplicate entities in a document.
        """

        merged_results = await self.providers.database.entities_handler.merge_duplicate_name_blocks(
            parent_id=document_id,
            store_type=StoreType.DOCUMENTS,
        )

        response = await self.providers.database.documents_handler.get_documents_overview(
            offset=0,
            limit=1,
            filter_document_ids=[document_id],
        )
        document_summary = (
            response["results"][0].summary if response["results"] else None
        )

        for original_entities, merged_entity in merged_results:
            # Generate new consolidated description using the LLM
            messages = await self.providers.database.prompts_handler.get_message_payload(
                task_prompt_name=self.providers.database.config.graph_creation_settings.graph_entity_description_prompt,
                task_inputs={
                    "document_summary": document_summary,
                    "entity_info": f"{merged_entity.name}\n".join(
                        [
                            desc
                            for desc in {
                                e.description for e in original_entities
                            }
                            if desc is not None
                        ]
                    ),
                    "relationships_txt": "",
                },
            )

            generation_config = (
                self.config.database.graph_creation_settings.generation_config
            )
            response = await self.providers.llm.aget_completion(
                messages,
                generation_config=generation_config,
            )
            new_description = response.choices[0].message.content

            # Generate new embedding for the consolidated description
            new_embedding = await self.providers.embedding.async_get_embedding(
                new_description
            )

            # Update the entity with new description and embedding
            await self.providers.database.graphs_handler.entities.update(
                entity_id=merged_entity.id,
                store_type=StoreType.DOCUMENTS,
                description=new_description,
                description_embedding=str(new_embedding),
            )
