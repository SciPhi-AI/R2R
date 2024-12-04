import asyncio
import json
import logging
import random
import time
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
from core.providers.database import PostgresDBProvider
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider

logger = logging.getLogger()


class KGCommunitySummaryPipe(AsyncPipe):
    """
    Clusters entities and relationships into communities within the knowledge graph using hierarchical Leiden algorithm.
    """

    def __init__(
        self,
        database_provider: PostgresDBProvider,
        llm_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
        config: AsyncPipe.PipeConfig,
        logging_provider: SqlitePersistentLoggingProvider,
        *args,
        **kwargs,
    ):
        """
        Initializes the KG clustering pipe with necessary components and configurations.
        """
        super().__init__(
            logging_provider=logging_provider,
            config=config
            or AsyncPipe.PipeConfig(name="kg_community_summary_pipe"),
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
        collection_id: UUID | None,
        nodes: list[str],
        all_entities: list[Entity],
        all_relationships: list[Relationship],
    ) -> dict:
        """
        Process a community by summarizing it and creating a summary embedding and storing it to a database.
        """

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

        for attempt in range(3):

            description = (
                (
                    await self.llm_provider.aget_completion(
                        messages=await self.database_provider.prompt_handler.get_message_payload(
                            task_prompt_name=self.database_provider.config.graph_enrichment_settings.graphrag_communities,
                            task_inputs={
                                "input_text": (
                                    await self.community_summary_prompt(
                                        entities,
                                        relationships,
                                        max_summary_input_length,
                                    )
                                ),
                            },
                        ),
                        generation_config=generation_config,
                    )
                )
                .choices[0]
                .message.content
            )

            try:
                if description and description.startswith("```json"):
                    description = (
                        description.strip("```json").strip("```").strip()
                    )
                else:
                    raise ValueError(
                        f"Failed to generate a summary for community {community_id}"
                    )

                description_dict = json.loads(description)
                name = description_dict["name"]
                summary = description_dict["summary"]
                findings = description_dict["findings"]
                rating = description_dict["rating"]
                rating_explanation = description_dict["rating_explanation"]
                break
            except Exception as e:
                if attempt == 2:
                    logger.error(
                        f"KGCommunitySummaryPipe: Error generating community summary for community {community_id}: {e}"
                    )
                    return {
                        "community_id": community_id,
                        "error": str(e),
                    }

        community = Community(
            community_id=community_id,
            collection_id=collection_id,
            name=name,
            summary=summary,
            rating=rating,
            rating_explanation=rating_explanation,
            findings=findings,
            description_embedding=await self.embedding_provider.async_get_embedding(
                "Summary:\n"
                + summary
                + "\n\nFindings:\n"
                + "\n".join(findings)
            ),
        )

        await self.database_provider.graph_handler.add_community(community)

        return {
            "community_id": community.community_id,
            "name": community.name,
        }

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
        community_summary_jobs = []
        logger = input.message.get("logger", logging.getLogger())

        # check which community summaries exist and don't run them again
        logger.info(
            f"KGCommunitySummaryPipe: Checking if community summaries exist for communities {offset} to {offset + limit}"
        )

        all_entities, _ = (
            await self.database_provider.graph_handler.get_entities(
                parent_id=collection_id,
                offset=0,
                limit=-1,
                include_embeddings=False,
            )
        )

        all_relationships, _ = (
            await self.database_provider.graph_handler.get_relationships(
                parent_id=collection_id,
                offset=0,
                limit=-1,
                include_embeddings=False,
            )
        )

        # Perform clustering
        leiden_params = input.message.get("leiden_params", {})
        _, community_clusters = (
            await self.database_provider.graph_handler._cluster_and_add_community_info(
                relationships=all_relationships,
                relationship_ids_cache={},
                leiden_params=leiden_params,
                collection_id=collection_id,
            )
        )

        # Organize clusters
        clusters: dict[Any] = {}
        for item in community_clusters:
            cluster_id = item.cluster
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(item.node)

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
                    f"KGCommunitySummaryPipe: {completed_community_summary_jobs}/{total_jobs} community summaries completed, elapsed time: {time.time() - start_time:.2f} seconds"
                )

            if "error" in summary:
                logger.error(
                    f"KGCommunitySummaryPipe: Error generating community summary for community {summary['community_id']}: {summary['error']}"
                )
                total_errors += 1
                continue

            yield summary

        if total_errors > 0:
            raise ValueError(
                f"KGCommunitySummaryPipe: Failed to generate community summaries for {total_errors} out of {total_jobs} communities. Please rerun the job if there are too many failures."
            )
