import asyncio
import logging
import random
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

from core.base import (
    AsyncPipe,
    AsyncState,
    Community,
    CompletionProvider,
    EmbeddingProvider,
    GenerationConfig,
)
from core.base.abstractions import Entity, Relationship

from ...database.postgres import PostgresDatabaseProvider

logger = logging.getLogger()


class GraphCommunitySummaryPipe(AsyncPipe):
    """
    Clusters entities and relationships into communities within the knowledge graph using hierarchical Leiden algorithm.
    """

    def __init__(
        self,
        database_provider: PostgresDatabaseProvider,
        llm_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
        config: AsyncPipe.PipeConfig,
        *args,
        **kwargs,
    ):
        """
        Initializes the KG clustering pipe with necessary components and configurations.
        """
        super().__init__(
            config=config
            or AsyncPipe.PipeConfig(name="graph_community_summary_pipe"),
        )
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def community_summary_prompt(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
        max_summary_input_length: int,
    ):
        entity_map: dict[str, dict[str, list[Any]]] = {}
        for entity in entities:
            if not entity.name in entity_map:
                entity_map[entity.name] = {"entities": [], "relationships": []}  # type: ignore
            entity_map[entity.name]["entities"].append(entity)  # type: ignore

        for relationship in relationships:
            if not relationship.subject in entity_map:
                entity_map[relationship.subject] = {  # type: ignore
                    "entities": [],
                    "relationships": [],
                }
            entity_map[relationship.subject]["relationships"].append(  # type: ignore
                relationship
            )

        # sort in descending order of relationship count
        sorted_entity_map = sorted(
            entity_map.items(),
            key=lambda x: len(x[1]["relationships"]),
            reverse=True,
        )

        async def _get_entity_descriptions_string(
            entities: list, max_count: int = 100
        ):
            # randomly sample max_count entities if there are duplicates. This will become a map reduce job later.
            sampled_entities = (
                random.sample(entities, max_count)
                if len(entities) > max_count
                else entities
            )
            return "\n".join(
                f"{entity.id},{entity.description}"
                for entity in sampled_entities
            )

        async def _get_relationships_string(
            relationships: list, max_count: int = 100
        ):
            sampled_relationships = (
                random.sample(relationships, max_count)
                if len(relationships) > max_count
                else relationships
            )
            return "\n".join(
                f"{relationship.id},{relationship.subject},{relationship.object},{relationship.predicate},{relationship.description}"
                for relationship in sampled_relationships
            )

        prompt = ""
        for entity_name, entity_data in sorted_entity_map:
            entity_descriptions = await _get_entity_descriptions_string(
                entity_data["entities"]
            )
            relationships = await _get_relationships_string(
                entity_data["relationships"]
            )

            prompt += f"""
            Entity: {entity_name}
            Descriptions:
                {entity_descriptions}
            Relationships:
                {relationships}
            """

            if len(prompt) > max_summary_input_length:
                logger.info(
                    f"Community summary prompt was created of length {len(prompt)}, trimming to {max_summary_input_length} characters."
                )
                # open a file and write the prompt to it
                prompt = prompt[:max_summary_input_length]
                break

        return prompt

    async def process_community(
        self,
        community_id: UUID,
        max_summary_input_length: int,
        generation_config: GenerationConfig,
        collection_id: UUID,
        nodes: list[str],
        all_entities: list[Entity],
        all_relationships: list[Relationship],
    ) -> dict:
        """
        Process a community by summarizing it and creating a summary embedding and storing it to a database.
        """

        response = await self.database_provider.collections_handler.get_collections_overview(
            offset=0,
            limit=1,
            filter_collection_ids=[collection_id],
        )
        collection_description = (
            response["results"][0].description if response["results"] else None
        )

        entities = [entity for entity in all_entities if entity.name in nodes]
        relationships = [
            relationship
            for relationship in all_relationships
            if relationship.subject in nodes and relationship.object in nodes
        ]

        if not entities and not relationships:
            raise ValueError(
                f"Community {community_id} has no entities or relationships."
            )

        input_text = await self.community_summary_prompt(
            entities,
            relationships,
            max_summary_input_length,
        )

        for attempt in range(3):
            try:
                description = (
                    (
                        await self.llm_provider.aget_completion(
                            messages=await self.database_provider.prompts_handler.get_message_payload(
                                task_prompt_name=self.database_provider.config.graph_enrichment_settings.graphrag_communities,
                                task_inputs={
                                    "collection_description": collection_description,
                                    "input_text": input_text,
                                },
                            ),
                            generation_config=generation_config,
                        )
                    )
                    .choices[0]
                    .message.content
                )

                # Extract XML content
                match = re.search(
                    r"<community>.*?</community>", description, re.DOTALL
                )
                if not match:
                    raise ValueError(
                        "Could not find community XML tags in response"
                    )

                xml_content = match.group(0)
                root = ET.fromstring(xml_content)

                # Extract available fields, defaulting to None if not found
                name = root.find("name")
                summary = root.find("summary")
                rating = root.find("rating")
                rating_explanation = root.find("rating_explanation")
                findings_elem = root.find("findings")

                community = Community(
                    community_id=community_id,
                    collection_id=collection_id,
                    name=name.text if name is not None else "",
                    summary=summary.text if summary is not None else "",
                    rating=float(rating.text) if rating is not None else None,
                    rating_explanation=(
                        rating_explanation.text
                        if rating_explanation is not None
                        else None
                    ),
                    findings=(
                        [f.text for f in findings_elem.findall("finding")]
                        if findings_elem is not None
                        else []
                    ),
                    description_embedding=await self.embedding_provider.async_get_embedding(
                        "Summary:\n"
                        + (summary.text if summary is not None else "")
                        + "\n\nFindings:\n"
                        + "\n".join(
                            [f.text for f in findings_elem.findall("finding")]
                            if findings_elem is not None
                            else []
                        )
                    ),
                )

                await self.database_provider.graphs_handler.add_community(
                    community
                )
                return {
                    "community_id": community.community_id,
                    "name": community.name,
                }

            except Exception as e:
                if attempt == 2:
                    logger.error(
                        f"GraphCommunitySummaryPipe: Error generating community summary for community {community_id}: {e}"
                    )
                    return {
                        "community_id": community_id,
                        "error": str(e),
                    }
                await asyncio.sleep(1)

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[dict, None]:
        """
        Executes the KG community summary pipe: summarizing communities.
        """

        start_time = time.time()

        offset = input.message["offset"]
        limit = input.message["limit"]
        generation_config = input.message["generation_config"]
        max_summary_input_length = input.message["max_summary_input_length"]
        collection_id = input.message.get("collection_id", None)
        clustering_mode = input.message.get("clustering_mode", None)
        community_summary_jobs = []
        logger = input.message.get("logger", logging.getLogger())

        # check which community summaries exist and don't run them again
        logger.info(
            f"GraphCommunitySummaryPipe: Checking if community summaries exist for communities {offset} to {offset + limit}"
        )

        (
            all_entities,
            _,
        ) = await self.database_provider.graphs_handler.get_entities(
            parent_id=collection_id,
            offset=0,
            limit=-1,
            include_embeddings=False,
        )

        (
            all_relationships,
            _,
        ) = await self.database_provider.graphs_handler.get_relationships(
            parent_id=collection_id,
            offset=0,
            limit=-1,
            include_embeddings=False,
        )

        # Perform clustering
        leiden_params = input.message.get("leiden_params", {})
        (
            _,
            community_clusters,
        ) = await self.database_provider.graphs_handler._cluster_and_add_community_info(
            relationships=all_relationships,
            leiden_params=leiden_params,
            collection_id=collection_id,
            clustering_mode=clustering_mode,
        )

        # Organize clusters
        clusters: dict[Any, Any] = {}
        for item in community_clusters:
            cluster_id = (
                item["cluster"]
                if clustering_mode == "remote"
                else item.cluster
            )
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(
                item["node"] if clustering_mode == "remote" else item.node
            )

        # Now, process the clusters
        for _, nodes in clusters.items():
            community_summary_jobs.append(
                self.process_community(
                    community_id=uuid4(),
                    nodes=nodes,
                    all_entities=all_entities,
                    all_relationships=all_relationships,
                    max_summary_input_length=max_summary_input_length,
                    generation_config=generation_config,
                    collection_id=collection_id,
                )
            )

        total_jobs = len(community_summary_jobs)
        total_errors = 0
        completed_community_summary_jobs = 0
        for community_summary in asyncio.as_completed(community_summary_jobs):
            summary = await community_summary
            completed_community_summary_jobs += 1
            if completed_community_summary_jobs % 50 == 0:
                logger.info(
                    f"GraphCommunitySummaryPipe: {completed_community_summary_jobs}/{total_jobs} community summaries completed, elapsed time: {time.time() - start_time:.2f} seconds"
                )

            if "error" in summary:
                logger.error(
                    f"GraphCommunitySummaryPipe: Error generating community summary for community {summary['community_id']}: {summary['error']}"
                )
                total_errors += 1
                continue

            yield summary

        if total_errors > 0:
            raise ValueError(
                f"GraphCommunitySummaryPipe: Failed to generate community summaries for {total_errors} out of {total_jobs} communities. Please rerun the job if there are too many failures."
            )
