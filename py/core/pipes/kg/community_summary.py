import asyncio
import json
import logging
import random
import time
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    CommunityReport,
    CompletionProvider,
    DatabaseProvider,
    EmbeddingProvider,
    GenerationConfig,
)
from core.base.abstractions import Entity, Relationship
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider

logger = logging.getLogger()


class KGCommunitySummaryPipe(AsyncPipe):
    """
    Clusters entities and triples into communities within the knowledge graph using hierarchical Leiden algorithm.
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
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
        triples: list[Relationship],
        max_summary_input_length: int,
    ):

        entity_map: dict[str, dict[str, list[Any]]] = {}
        for entity in entities:
            if not entity.name in entity_map:
                entity_map[entity.name] = {"entities": [], "triples": []}
            entity_map[entity.name]["entities"].append(entity)

        for triple in triples:
            if not triple.subject in entity_map:
                entity_map[triple.subject] = {
                    "entities": [],
                    "triples": [],
                }
            entity_map[triple.subject]["triples"].append(triple)

        # sort in descending order of triple count
        sorted_entity_map = sorted(
            entity_map.items(),
            key=lambda x: len(x[1]["triples"]),
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

        async def _get_triples_string(triples: list, max_count: int = 100):
            sampled_triples = (
                random.sample(triples, max_count)
                if len(triples) > max_count
                else triples
            )
            return "\n".join(
                f"{triple.id},{triple.subject},{triple.object},{triple.predicate},{triple.description}"
                for triple in sampled_triples
            )

        prompt = ""
        for entity_name, entity_data in sorted_entity_map:
            entity_descriptions = await _get_entity_descriptions_string(
                entity_data["entities"]
            )
            triples = await _get_triples_string(entity_data["triples"])

            prompt += f"""
            Entity: {entity_name}
            Descriptions:
                {entity_descriptions}
            Triples:
                {triples}
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
        community_number: int,
        max_summary_input_length: int,
        generation_config: GenerationConfig,
        collection_id: UUID,
    ) -> dict:
        """
        Process a community by summarizing it and creating a summary embedding and storing it to a database.
        """

        community_level, entities, triples = (
            await self.database_provider.get_community_details(
                community_number=community_number,
                collection_id=collection_id,
            )
        )

        if entities == [] and triples == []:
            raise ValueError(
                f"Community {community_number} has no entities or triples."
            )

        for attempt in range(3):

            description = (
                (
                    await self.llm_provider.aget_completion(
                        messages=await self.database_provider.prompt_handler.get_message_payload(
                            task_prompt_name=self.database_provider.config.kg_enrichment_settings.graphrag_community_reports,
                            task_inputs={
                                "input_text": (
                                    await self.community_summary_prompt(
                                        entities,
                                        triples,
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
                        f"Failed to generate a summary for community {community_number} at level {community_level}."
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
                        f"KGCommunitySummaryPipe: Error generating community summary for community {community_number}: {e}"
                    )
                    return {
                        "community_number": community_number,
                        "error": str(e),
                    }

        community_report = CommunityReport(
            community_number=community_number,
            collection_id=collection_id,
            level=community_level,
            name=name,
            summary=summary,
            rating=rating,
            rating_explanation=rating_explanation,
            findings=findings,
            embedding=await self.embedding_provider.async_get_embedding(
                "Summary:\n"
                + summary
                + "\n\nFindings:\n"
                + "\n".join(findings)
            ),
        )

        await self.database_provider.add_community_report(community_report)

        return {
            "community_number": community_report.community_number,
            "name": community_report.name,
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
        collection_id = input.message["collection_id"]
        community_summary_jobs = []
        logger = input.message.get("logger", logging.getLogger())

        # check which community summaries exist and don't run them again
        logger.info(
            f"KGCommunitySummaryPipe: Checking if community summaries exist for communities {offset} to {offset + limit}"
        )
        community_numbers_exist = (
            await self.database_provider.check_community_reports_exist(
                collection_id=collection_id, offset=offset, limit=limit
            )
        )

        logger.info(
            f"KGCommunitySummaryPipe: Community summaries exist for communities {len(community_numbers_exist)}"
        )

        for community_number in range(offset, offset + limit):
            if community_number not in community_numbers_exist:
                community_summary_jobs.append(
                    self.process_community(
                        community_number=community_number,
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
                    f"KGCommunitySummaryPipe: Error generating community summary for community {summary['community_number']}: {summary['error']}"
                )
                total_errors += 1
                continue

            yield summary

        if total_errors > 0:
            raise ValueError(
                f"KGCommunitySummaryPipe: Failed to generate community summaries for {total_errors} out of {total_jobs} communities. Please rerun the job if there are too many failures."
            )
