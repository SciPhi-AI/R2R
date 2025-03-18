import asyncio
import logging
import math
import random
import re
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Any, AsyncGenerator, Coroutine, Optional
from uuid import UUID
from xml.etree.ElementTree import Element

from core.base import (
    DocumentChunk,
    GraphExtraction,
    GraphExtractionStatus,
    R2RDocumentProcessingError,
)
from core.base.abstractions import (
    Community,
    Entity,
    GenerationConfig,
    GraphConstructionStatus,
    R2RException,
    Relationship,
    StoreType,
)
from core.base.api.models import GraphResponse

from ..abstractions import R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger()

MIN_VALID_GRAPH_EXTRACTION_RESPONSE_LENGTH = 128


async def _collect_async_results(result_gen: AsyncGenerator) -> list[Any]:
    """Collects all results from an async generator into a list."""
    results = []
    async for res in result_gen:
        results.append(res)
    return results


class GraphService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
    ):
        super().__init__(
            config,
            providers,
        )

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

    async def delete_community(
        self,
        parent_id: UUID,
        community_id: UUID,
    ) -> None:
        await self.providers.database.graphs_handler.communities.delete(
            parent_id=parent_id,
            community_id=community_id,
        )

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
        graph_ids: Optional[list[UUID]] = None,
        collection_id: Optional[UUID] = None,
    ) -> dict[str, list[GraphResponse] | int]:
        return await self.providers.database.graphs_handler.list_graphs(
            offset=offset,
            limit=limit,
            filter_graph_ids=graph_ids,
            filter_collection_id=collection_id,
        )

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

    async def reset_graph(self, id: UUID) -> bool:
        await self.providers.database.graphs_handler.reset(
            parent_id=id,
        )
        await self.providers.database.documents_handler.set_workflow_status(
            id=id,
            status_type="graph_cluster_status",
            status=GraphConstructionStatus.PENDING,
        )
        return True

    async def get_document_ids_for_create_graph(
        self,
        collection_id: UUID,
        **kwargs,
    ):
        document_status_filter = [
            GraphExtractionStatus.PENDING,
            GraphExtractionStatus.FAILED,
        ]

        return await self.providers.database.documents_handler.get_document_ids_by_status(
            status_type="extraction_status",
            status=[str(ele) for ele in document_status_filter],
            collection_id=collection_id,
        )

    async def graph_search_results_entity_description(
        self,
        document_id: UUID,
        max_description_input_length: int,
        batch_size: int = 256,
        **kwargs,
    ):
        """A new implementation of the old GraphDescriptionPipe logic inline.
        No references to pipe objects.

        We:
         1) Count how many entities are in the document
         2) Process them in batches of `batch_size`
         3) For each batch, we retrieve the entity map and possibly call LLM for missing descriptions
        """
        start_time = time.time()
        logger.info(
            f"GraphService: Running graph_search_results_entity_description for doc={document_id}"
        )

        # Count how many doc-entities exist
        entity_count = (
            await self.providers.database.graphs_handler.get_entity_count(
                document_id=document_id,
                distinct=True,
                entity_table_name="documents_entities",  # or whichever table
            )
        )
        logger.info(
            f"GraphService: Found {entity_count} doc-entities to describe."
        )

        all_results = []
        num_batches = math.ceil(entity_count / batch_size)

        for i in range(num_batches):
            offset = i * batch_size
            limit = batch_size

            logger.info(
                f"GraphService: describing batch {i + 1}/{num_batches}, offset={offset}, limit={limit}"
            )

            # Actually handle describing the entities in the batch
            # We'll collect them into a list via an async generator
            gen = self._describe_entities_in_document_batch(
                document_id=document_id,
                offset=offset,
                limit=limit,
                max_description_input_length=max_description_input_length,
            )
            batch_results = await _collect_async_results(gen)
            all_results.append(batch_results)

        # Mark the doc's extraction status as success
        await self.providers.database.documents_handler.set_workflow_status(
            id=document_id,
            status_type="extraction_status",
            status=GraphExtractionStatus.SUCCESS,
        )
        logger.info(
            f"GraphService: Completed graph_search_results_entity_description for doc {document_id} in {time.time() - start_time:.2f}s."
        )
        return all_results

    async def _describe_entities_in_document_batch(
        self,
        document_id: UUID,
        offset: int,
        limit: int,
        max_description_input_length: int,
    ) -> AsyncGenerator[str, None]:
        """Core logic that replaces GraphDescriptionPipe._run_logic for a
        particular document/batch.

        Yields entity-names or some textual result as each entity is updated.
        """
        start_time = time.time()
        logger.info(
            f"Started describing doc={document_id}, offset={offset}, limit={limit}"
        )

        # 1) Get the "entity map" from the DB
        entity_map = (
            await self.providers.database.graphs_handler.get_entity_map(
                offset=offset, limit=limit, document_id=document_id
            )
        )
        total_entities = len(entity_map)
        logger.info(
            f"_describe_entities_in_document_batch: got {total_entities} items in entity_map for doc={document_id}."
        )

        # 2) For each entity name in the map, we gather sub-entities and relationships
        tasks: list[Coroutine[Any, Any, str]] = []
        tasks.extend(
            self._process_entity_for_description(
                entities=[
                    entity if isinstance(entity, Entity) else Entity(**entity)
                    for entity in entity_info["entities"]
                ],
                relationships=[
                    rel
                    if isinstance(rel, Relationship)
                    else Relationship(**rel)
                    for rel in entity_info["relationships"]
                ],
                document_id=document_id,
                max_description_input_length=max_description_input_length,
            )
            for entity_name, entity_info in entity_map.items()
        )

        # 3) Wait for all tasks, yield as they complete
        idx = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            idx += 1
            if idx % 100 == 0:
                logger.info(
                    f"_describe_entities_in_document_batch: {idx}/{total_entities} described for doc={document_id}"
                )
            yield result

        logger.info(
            f"Finished describing doc={document_id} batch offset={offset} in {time.time() - start_time:.2f}s."
        )

    async def _process_entity_for_description(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
        document_id: UUID,
        max_description_input_length: int,
    ) -> str:
        """Adapted from the old process_entity function in
        GraphDescriptionPipe.

        If entity has no description, call an LLM to create one, then store it.
        Returns the name of the top entity (or could store more details).
        """

        def truncate_info(info_list: list[str], max_length: int) -> str:
            """Shuffles lines of info to try to keep them distinct, then
            accumulates until hitting max_length."""
            random.shuffle(info_list)
            truncated_info = ""
            current_length = 0
            for info in info_list:
                if current_length + len(info) > max_length:
                    break
                truncated_info += info + "\n"
                current_length += len(info)
            return truncated_info

        # Grab a doc-level summary (optional) to feed into the prompt
        response = await self.providers.database.documents_handler.get_documents_overview(
            offset=0,
            limit=1,
            filter_document_ids=[document_id],
        )
        document_summary = (
            response["results"][0].summary if response["results"] else None
        )

        # Synthesize a minimal “entity info” string + relationship summary
        entity_info = [
            f"{e.name}, {e.description or 'NONE'}" for e in entities
        ]
        relationships_txt = [
            f"{i + 1}: {r.subject}, {r.object}, {r.predicate} - Summary: {r.description or ''}"
            for i, r in enumerate(relationships)
        ]

        # We'll describe only the first entity for simplicity
        # or you could do them all if needed
        main_entity = entities[0]

        if not main_entity.description:
            # We only call LLM if the entity is missing a description
            messages = await self.providers.database.prompts_handler.get_message_payload(
                task_prompt_name=self.providers.database.config.graph_creation_settings.graph_entity_description_prompt,
                task_inputs={
                    "document_summary": document_summary,
                    "entity_info": truncate_info(
                        entity_info, max_description_input_length
                    ),
                    "relationships_txt": truncate_info(
                        relationships_txt, max_description_input_length
                    ),
                },
            )

            # Call the LLM
            gen_config = (
                self.providers.database.config.graph_creation_settings.generation_config
                or GenerationConfig(model=self.config.app.fast_llm)
            )
            llm_resp = await self.providers.llm.aget_completion(
                messages=messages,
                generation_config=gen_config,
            )
            new_description = llm_resp.choices[0].message.content

            if not new_description:
                logger.error(
                    f"No LLM description returned for entity={main_entity.name}"
                )
                return main_entity.name

            # create embedding
            embed = (
                await self.providers.embedding.async_get_embeddings(
                    [new_description]
                )
            )[0]

            # update DB
            main_entity.description = new_description
            main_entity.description_embedding = embed

            # Use a method to upsert entity in `documents_entities` or your table
            await self.providers.database.graphs_handler.add_entities(
                [main_entity],
                table_name="documents_entities",
            )

        return main_entity.name

    async def graph_search_results_clustering(
        self,
        collection_id: UUID,
        generation_config: GenerationConfig,
        leiden_params: dict,
        **kwargs,
    ):
        """
        Replacement for the old GraphClusteringPipe logic:
          1) call perform_graph_clustering on the DB
          2) return the result
        """
        logger.info(
            f"Running inline clustering for collection={collection_id} with params={leiden_params}"
        )
        return await self._perform_graph_clustering(
            collection_id=collection_id,
            generation_config=generation_config,
            leiden_params=leiden_params,
        )

    async def _perform_graph_clustering(
        self,
        collection_id: UUID,
        generation_config: GenerationConfig,
        leiden_params: dict,
    ) -> dict:
        """The actual clustering logic (previously in
        GraphClusteringPipe.cluster_graph_search_results)."""
        num_communities = await self.providers.database.graphs_handler.perform_graph_clustering(
            collection_id=collection_id,
            leiden_params=leiden_params,
        )
        return {"num_communities": num_communities}

    async def graph_search_results_community_summary(
        self,
        offset: int,
        limit: int,
        max_summary_input_length: int,
        generation_config: GenerationConfig,
        collection_id: UUID,
        leiden_params: Optional[dict] = None,
        **kwargs,
    ):
        """Replacement for the old GraphCommunitySummaryPipe logic.

        Summarizes communities after clustering. Returns an async generator or
        you can collect into a list.
        """
        logger.info(
            f"Running inline community summaries for coll={collection_id}, offset={offset}, limit={limit}"
        )
        # We call an internal function that yields summaries
        gen = self._summarize_communities(
            offset=offset,
            limit=limit,
            max_summary_input_length=max_summary_input_length,
            generation_config=generation_config,
            collection_id=collection_id,
            leiden_params=leiden_params or {},
        )
        return await _collect_async_results(gen)

    async def _summarize_communities(
        self,
        offset: int,
        limit: int,
        max_summary_input_length: int,
        generation_config: GenerationConfig,
        collection_id: UUID,
        leiden_params: dict,
    ) -> AsyncGenerator[dict, None]:
        """Does the community summary logic from
        GraphCommunitySummaryPipe._run_logic.

        Yields each summary dictionary as it completes.
        """
        start_time = time.time()
        logger.info(
            f"Starting community summarization for collection={collection_id}"
        )

        # get all entities & relationships
        (
            all_entities,
            _,
        ) = await self.providers.database.graphs_handler.get_entities(
            parent_id=collection_id,
            offset=0,
            limit=-1,
            include_embeddings=False,
        )
        (
            all_relationships,
            _,
        ) = await self.providers.database.graphs_handler.get_relationships(
            parent_id=collection_id,
            offset=0,
            limit=-1,
            include_embeddings=False,
        )

        # We can optionally re-run the clustering to produce fresh community assignments
        (
            _,
            community_clusters,
        ) = await self.providers.database.graphs_handler._cluster_and_add_community_info(
            relationships=all_relationships,
            leiden_params=leiden_params,
            collection_id=collection_id,
        )

        # Group clusters
        clusters: dict[Any, list[str]] = {}
        for item in community_clusters:
            cluster_id = item["cluster"]
            node_name = item["node"]
            clusters.setdefault(cluster_id, []).append(node_name)

        # create an async job for each cluster
        tasks: list[Coroutine[Any, Any, dict]] = []

        tasks.extend(
            self._process_community_summary(
                community_id=uuid.uuid4(),
                nodes=nodes,
                all_entities=all_entities,
                all_relationships=all_relationships,
                max_summary_input_length=max_summary_input_length,
                generation_config=generation_config,
                collection_id=collection_id,
            )
            for nodes in clusters.values()
        )

        total_jobs = len(tasks)
        results_returned = 0
        total_errors = 0

        for coro in asyncio.as_completed(tasks):
            summary = await coro
            results_returned += 1
            if results_returned % 50 == 0:
                logger.info(
                    f"Community summaries: {results_returned}/{total_jobs} done in {time.time() - start_time:.2f}s"
                )
            if "error" in summary:
                total_errors += 1
            yield summary

        if total_errors > 0:
            logger.warning(
                f"{total_errors} communities failed summarization out of {total_jobs}"
            )

    async def _process_community_summary(
        self,
        community_id: UUID,
        nodes: list[str],
        all_entities: list[Entity],
        all_relationships: list[Relationship],
        max_summary_input_length: int,
        generation_config: GenerationConfig,
        collection_id: UUID,
    ) -> dict:
        """
        Summarize a single community: gather all relevant entities/relationships, call LLM to generate an XML block,
        parse it, store the result as a community in DB.
        """
        # (Equivalent to process_community in old code)
        # fetch the collection description (optional)
        response = await self.providers.database.collections_handler.get_collections_overview(
            offset=0,
            limit=1,
            filter_collection_ids=[collection_id],
        )
        collection_description = (
            response["results"][0].description if response["results"] else None  # type: ignore
        )

        # filter out relevant entities / relationships
        entities = [e for e in all_entities if e.name in nodes]
        relationships = [
            r
            for r in all_relationships
            if r.subject in nodes and r.object in nodes
        ]
        if not entities and not relationships:
            return {
                "community_id": community_id,
                "error": f"No data in this community (nodes={nodes})",
            }

        # Create the big input text for the LLM
        input_text = await self._community_summary_prompt(
            entities,
            relationships,
            max_summary_input_length,
        )

        # Attempt up to 3 times to parse
        for attempt in range(3):
            try:
                # Build the prompt
                messages = await self.providers.database.prompts_handler.get_message_payload(
                    task_prompt_name=self.providers.database.config.graph_enrichment_settings.graph_communities_prompt,
                    task_inputs={
                        "collection_description": collection_description,
                        "input_text": input_text,
                    },
                )
                llm_resp = await self.providers.llm.aget_completion(
                    messages=messages,
                    generation_config=generation_config,
                )
                llm_text = llm_resp.choices[0].message.content or ""

                # find <community>...</community> XML
                match = re.search(
                    r"<community>.*?</community>", llm_text, re.DOTALL
                )
                if not match:
                    raise ValueError(
                        "No <community> XML found in LLM response"
                    )

                xml_content = match.group(0)
                root = ET.fromstring(xml_content)

                # extract fields
                name_elem = root.find("name")
                summary_elem = root.find("summary")
                rating_elem = root.find("rating")
                rating_expl_elem = root.find("rating_explanation")
                findings_elem = root.find("findings")

                name = name_elem.text if name_elem is not None else ""
                summary = summary_elem.text if summary_elem is not None else ""
                rating = (
                    float(rating_elem.text)
                    if isinstance(rating_elem, Element) and rating_elem.text
                    else ""
                )
                rating_explanation = (
                    rating_expl_elem.text
                    if rating_expl_elem is not None
                    else None
                )
                findings = (
                    [f.text for f in findings_elem.findall("finding")]
                    if findings_elem is not None
                    else []
                )

                # build embedding
                embed_text = (
                    "Summary:\n"
                    + (summary or "")
                    + "\n\nFindings:\n"
                    + "\n".join(
                        finding for finding in findings if finding is not None
                    )
                )
                embedding = await self.providers.embedding.async_get_embedding(
                    embed_text
                )

                # build Community object
                community = Community(
                    community_id=community_id,
                    collection_id=collection_id,
                    name=name,
                    summary=summary,
                    rating=rating,
                    rating_explanation=rating_explanation,
                    findings=findings,
                    description_embedding=embedding,
                )

                # store it
                await self.providers.database.graphs_handler.add_community(
                    community
                )

                return {
                    "community_id": community_id,
                    "name": name,
                }

            except Exception as e:
                logger.error(
                    f"Error summarizing community {community_id}: {e}"
                )
                if attempt == 2:
                    return {"community_id": community_id, "error": str(e)}
                await asyncio.sleep(1)

        # fallback
        return {"community_id": community_id, "error": "Failed after retries"}

    async def _community_summary_prompt(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
        max_summary_input_length: int,
    ) -> str:
        """Gathers the entity/relationship text, tries not to exceed
        `max_summary_input_length`."""
        # Group them by entity.name
        entity_map: dict[str, dict] = {}
        for e in entities:
            entity_map.setdefault(
                e.name, {"entities": [], "relationships": []}
            )
            entity_map[e.name]["entities"].append(e)

        for r in relationships:
            # subject
            entity_map.setdefault(
                r.subject, {"entities": [], "relationships": []}
            )
            entity_map[r.subject]["relationships"].append(r)

        # sort by # of relationships
        sorted_entries = sorted(
            entity_map.items(),
            key=lambda x: len(x[1]["relationships"]),
            reverse=True,
        )

        # build up the prompt text
        prompt_chunks = []
        cur_len = 0
        for entity_name, data in sorted_entries:
            block = f"\nEntity: {entity_name}\nDescriptions:\n"
            block += "\n".join(
                f"{e.id},{(e.description or '')}" for e in data["entities"]
            )
            block += "\nRelationships:\n"
            block += "\n".join(
                f"{r.id},{r.subject},{r.object},{r.predicate},{r.description or ''}"
                for r in data["relationships"]
            )
            # check length
            if cur_len + len(block) > max_summary_input_length:
                prompt_chunks.append(
                    block[: max_summary_input_length - cur_len]
                )
                break
            else:
                prompt_chunks.append(block)
                cur_len += len(block)

        return "".join(prompt_chunks)

    async def delete(
        self,
        collection_id: UUID,
        **kwargs,
    ):
        return await self.providers.database.graphs_handler.delete(
            collection_id=collection_id,
        )

    async def graph_search_results_extraction(
        self,
        document_id: UUID,
        generation_config: GenerationConfig,
        entity_types: list[str],
        relation_types: list[str],
        chunk_merge_count: int,
        filter_out_existing_chunks: bool = True,
        total_tasks: Optional[int] = None,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[GraphExtraction | R2RDocumentProcessingError, None]:
        """The original “extract Graph from doc” logic, but inlined instead of
        referencing a pipe."""
        start_time = time.time()

        logger.info(
            f"Graph Extraction: Processing document {document_id} for graph extraction"
        )

        # Retrieve chunks from DB
        chunks = []
        limit = 100
        offset = 0
        while True:
            chunk_req = await self.providers.database.chunks_handler.list_document_chunks(
                document_id=document_id,
                offset=offset,
                limit=limit,
            )
            new_chunk_objs = [
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
            chunks.extend(new_chunk_objs)
            if len(chunk_req["results"]) < limit:
                break
            offset += limit

        if not chunks:
            logger.info(f"No chunks found for document {document_id}")
            raise R2RException(
                message="No chunks found for document",
                status_code=404,
            )

        # Possibly filter out any chunks that have already been processed
        if filter_out_existing_chunks:
            existing_chunk_ids = await self.providers.database.graphs_handler.get_existing_document_entity_chunk_ids(
                document_id=document_id
            )
            before_count = len(chunks)
            chunks = [c for c in chunks if c.id not in existing_chunk_ids]
            logger.info(
                f"Filtered out {len(existing_chunk_ids)} existing chunk-IDs. {before_count}->{len(chunks)} remain."
            )
            if not chunks:
                return  # nothing left to yield

        # sort by chunk_order if present
        chunks = sorted(
            chunks,
            key=lambda x: x.metadata.get("chunk_order", float("inf")),
        )

        # group them
        grouped_chunks = [
            chunks[i : i + chunk_merge_count]
            for i in range(0, len(chunks), chunk_merge_count)
        ]

        logger.info(
            f"Graph Extraction: Created {len(grouped_chunks)} tasks for doc={document_id}"
        )
        tasks = [
            asyncio.create_task(
                self._extract_graph_search_results_from_chunk_group(
                    chunk_group,
                    generation_config,
                    entity_types,
                    relation_types,
                )
            )
            for chunk_group in grouped_chunks
        ]

        completed_tasks = 0
        for t in asyncio.as_completed(tasks):
            try:
                yield await t
                completed_tasks += 1
                if completed_tasks % 100 == 0:
                    logger.info(
                        f"Graph Extraction: completed {completed_tasks}/{len(tasks)} tasks"
                    )
            except Exception as e:
                logger.error(f"Error extracting from chunk group: {e}")
                yield R2RDocumentProcessingError(
                    document_id=document_id,
                    error_message=str(e),
                )

        logger.info(
            f"Graph Extraction: done with {document_id}, time={time.time() - start_time:.2f}s"
        )

    async def _extract_graph_search_results_from_chunk_group(
        self,
        chunks: list[DocumentChunk],
        generation_config: GenerationConfig,
        entity_types: list[str],
        relation_types: list[str],
        retries: int = 5,
        delay: int = 2,
    ) -> GraphExtraction:
        """(Equivalent to _extract_graph_search_results in old code.) Merges
        chunk data, calls LLM, parses XML, returns GraphExtraction object."""
        combined_extraction: str = " ".join(
            [
                c.data.decode("utf-8") if isinstance(c.data, bytes) else c.data
                for c in chunks
                if c.data
            ]
        )

        # Possibly get doc-level summary
        doc_id = chunks[0].document_id
        response = await self.providers.database.documents_handler.get_documents_overview(
            offset=0,
            limit=1,
            filter_document_ids=[doc_id],
        )
        document_summary = (
            response["results"][0].summary if response["results"] else None
        )

        # Build messages/prompt
        prompt_name = self.providers.database.config.graph_creation_settings.graph_extraction_prompt
        messages = (
            await self.providers.database.prompts_handler.get_message_payload(
                task_prompt_name=prompt_name,
                task_inputs={
                    "document_summary": document_summary or "",
                    "input": combined_extraction,
                    "entity_types": "\n".join(entity_types),
                    "relation_types": "\n".join(relation_types),
                },
            )
        )

        for attempt in range(retries):
            try:
                resp = await self.providers.llm.aget_completion(
                    messages, generation_config=generation_config
                )
                graph_search_results_str = resp.choices[0].message.content

                if not graph_search_results_str:
                    raise R2RException(
                        "No extraction found in LLM response.",
                        400,
                    )

                # parse the XML
                (
                    entities,
                    relationships,
                ) = await self._parse_graph_search_results_extraction_xml(
                    graph_search_results_str, chunks
                )
                return GraphExtraction(
                    entities=entities, relationships=relationships
                )

            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"All extraction attempts for doc={doc_id} and chunks{[chunk.id for chunk in chunks]} failed with error:\n{e}"
                    )
                    return GraphExtraction(entities=[], relationships=[])

        return GraphExtraction(entities=[], relationships=[])

    async def _parse_graph_search_results_extraction_xml(
        self, response_str: str, chunks: list[DocumentChunk]
    ) -> tuple[list[Entity], list[Relationship]]:
        """Helper to parse the LLM's XML format, handle edge cases/cleanup,
        produce Entities/Relationships."""

        def sanitize_xml(r: str) -> str:
            # Remove markdown fences
            r = re.sub(r"```xml|```", "", r)
            # Remove xml instructions or userStyle
            r = re.sub(r"<\?.*?\?>", "", r)
            r = re.sub(r"<userStyle>.*?</userStyle>", "", r)
            # Replace bare `&` with `&amp;`
            r = re.sub(r"&(?!amp;|quot;|apos;|lt;|gt;)", "&amp;", r)
            # Also remove <root> if it appears
            r = r.replace("<root>", "").replace("</root>", "")
            return r.strip()

        cleaned_xml = sanitize_xml(response_str)
        wrapped = f"<root>{cleaned_xml}</root>"
        try:
            root = ET.fromstring(wrapped)
        except ET.ParseError:
            raise R2RException(
                f"Failed to parse XML:\nData: {wrapped[:1000]}...", 400
            ) from None

        entities_elems = root.findall(".//entity")
        if (
            len(response_str) > MIN_VALID_GRAPH_EXTRACTION_RESPONSE_LENGTH
            and len(entities_elems) == 0
        ):
            raise R2RException(
                f"No <entity> found in LLM XML, possibly malformed. Response excerpt: {response_str[:300]}",
                400,
            )

        # build entity objects
        doc_id = chunks[0].document_id
        chunk_ids = [c.id for c in chunks]
        entities_list: list[Entity] = []
        for element in entities_elems:
            name_attr = element.get("name")
            type_elem = element.find("type")
            desc_elem = element.find("description")
            category = type_elem.text if type_elem is not None else None
            desc = desc_elem.text if desc_elem is not None else None
            desc_embed = await self.providers.embedding.async_get_embedding(
                desc or ""
            )
            ent = Entity(
                category=category,
                description=desc,
                name=name_attr,
                parent_id=doc_id,
                chunk_ids=chunk_ids,
                description_embedding=desc_embed,
                attributes={},
            )
            entities_list.append(ent)

        # build relationship objects
        relationships_list: list[Relationship] = []
        rel_elems = root.findall(".//relationship")
        for r_elem in rel_elems:
            source_elem = r_elem.find("source")
            target_elem = r_elem.find("target")
            type_elem = r_elem.find("type")
            desc_elem = r_elem.find("description")
            weight_elem = r_elem.find("weight")
            try:
                subject = source_elem.text if source_elem is not None else ""
                object_ = target_elem.text if target_elem is not None else ""
                predicate = type_elem.text if type_elem is not None else ""
                desc = desc_elem.text if desc_elem is not None else ""
                weight = (
                    float(weight_elem.text)
                    if isinstance(weight_elem, Element) and weight_elem.text
                    else ""
                )
                embed = await self.providers.embedding.async_get_embedding(
                    desc or ""
                )

                rel = Relationship(
                    subject=subject,
                    predicate=predicate,
                    object=object_,
                    description=desc,
                    weight=weight,
                    parent_id=doc_id,
                    chunk_ids=chunk_ids,
                    attributes={},
                    description_embedding=embed,
                )
                relationships_list.append(rel)
            except Exception:
                continue
        return entities_list, relationships_list

    async def store_graph_search_results_extractions(
        self,
        graph_search_results_extractions: list[GraphExtraction],
    ):
        """Stores a batch of knowledge graph extractions in the DB."""
        for extraction in graph_search_results_extractions:
            # Map name->id after creation
            entities_id_map = {}
            for e in extraction.entities:
                if e.parent_id is not None:
                    result = await self.providers.database.graphs_handler.entities.create(
                        name=e.name,
                        parent_id=e.parent_id,
                        store_type=StoreType.DOCUMENTS,
                        category=e.category,
                        description=e.description,
                        description_embedding=e.description_embedding,
                        chunk_ids=e.chunk_ids,
                        metadata=e.metadata,
                    )
                    entities_id_map[e.name] = result.id
                else:
                    logger.warning(f"Skipping entity with None parent_id: {e}")

            # Insert relationships
            for rel in extraction.relationships:
                subject_id = entities_id_map.get(rel.subject)
                object_id = entities_id_map.get(rel.object)
                parent_id = rel.parent_id

                if any(
                    id is None for id in (subject_id, object_id, parent_id)
                ):
                    logger.warning(f"Missing ID for relationship: {rel}")
                    continue

                assert isinstance(subject_id, UUID)
                assert isinstance(object_id, UUID)
                assert isinstance(parent_id, UUID)

                await self.providers.database.graphs_handler.relationships.create(
                    subject=rel.subject,
                    subject_id=subject_id,
                    predicate=rel.predicate,
                    object=rel.object,
                    object_id=object_id,
                    parent_id=parent_id,
                    description=rel.description,
                    description_embedding=rel.description_embedding,
                    weight=rel.weight,
                    metadata=rel.metadata,
                    store_type=StoreType.DOCUMENTS,
                )

    async def deduplicate_document_entities(
        self,
        document_id: UUID,
    ):
        """
        Inlined from old code: merges duplicates by name, calls LLM for a new consolidated description, updates the record.
        """
        merged_results = await self.providers.database.entities_handler.merge_duplicate_name_blocks(
            parent_id=document_id,
            store_type=StoreType.DOCUMENTS,
        )

        # Grab doc summary
        response = await self.providers.database.documents_handler.get_documents_overview(
            offset=0,
            limit=1,
            filter_document_ids=[document_id],
        )
        document_summary = (
            response["results"][0].summary if response["results"] else None
        )

        # For each merged entity
        for original_entities, merged_entity in merged_results:
            # Summarize them with LLM
            entity_info = "\n".join(
                e.description for e in original_entities if e.description
            )
            messages = await self.providers.database.prompts_handler.get_message_payload(
                task_prompt_name=self.providers.database.config.graph_creation_settings.graph_entity_description_prompt,
                task_inputs={
                    "document_summary": document_summary,
                    "entity_info": f"{merged_entity.name}\n{entity_info}",
                    "relationships_txt": "",
                },
            )
            gen_config = (
                self.config.database.graph_creation_settings.generation_config
                or GenerationConfig(model=self.config.app.fast_llm)
            )
            resp = await self.providers.llm.aget_completion(
                messages, generation_config=gen_config
            )
            new_description = resp.choices[0].message.content

            new_embedding = await self.providers.embedding.async_get_embedding(
                new_description or ""
            )

            if merged_entity.id is not None:
                await self.providers.database.graphs_handler.entities.update(
                    entity_id=merged_entity.id,
                    store_type=StoreType.DOCUMENTS,
                    description=new_description,
                    description_embedding=str(new_embedding),
                )
            else:
                logger.warning("Skipping update for entity with None id")
