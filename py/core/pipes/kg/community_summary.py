import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    Community,
    CommunityReport,
    CompletionProvider,
    EmbeddingProvider,
    Entity,
    GenerationConfig,
    KGProvider,
    PipeType,
    PromptProvider,
    RunLoggingSingleton,
    Triple,
)

logger = logging.getLogger(__name__)


class KGCommunitySummaryPipe(AsyncPipe):
    """
    Clusters entities and triples into communities within the knowledge graph using hierarchical Leiden algorithm.
    """

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        embedding_provider: EmbeddingProvider,
        config: AsyncPipe.PipeConfig,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        *args,
        **kwargs,
    ):
        """
        Initializes the KG clustering pipe with necessary components and configurations.
        """
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config
            or AsyncPipe.PipeConfig(name="kg_community_summary_pipe"),
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider
        self.embedding_provider = embedding_provider

    def community_summary_prompt(
        self,
        entities: list,
        triples: list,
        max_summary_input_length: int,
    ):
        """
        Preparing the list of entities and triples to be summarized and created into a community summary.
        """
        entities_info = "\n".join(
            [
                f"{entity['id']}, {entity['name']}, {entity['description']}"
                for entity in entities
            ]
        )

        triples_info = "\n".join(
            [
                f"{triple['id']}, {triple['subject']}, {triple['object']}, {triple['predicate']}, {triple['description']}"
                for triple in triples
            ]
        )

        prompt = f"""
        Entities:
        {entities_info}

        Relationships:
        {triples_info}
        """

        if len(prompt) > max_summary_input_length:
            logger.info(
                f"Community summary prompt was created of length {len(prompt)}, trimming to {max_summary_input_length} characters."
            )
            prompt = prompt[:max_summary_input_length]

        return prompt

    async def process_community(
        self,
        project_name: str,
        community_id: str,
        max_summary_input_length: int,
        generation_config: GenerationConfig,
        collection_id: UUID,
    ) -> dict:
        """
        Process a community by summarizing it and creating a summary embedding and storing it to a database.
        """

        community_level, entities, triples = (
            await self.kg_provider.get_community_details(
                project_name=project_name, community_id=community_id
            )
        )

        if entities == [] or triples == []:
            raise ValueError(
                f"Community {community_id} has no entities or triples."
            )

        for attempt in range(3):

            description = (
                (
                    await self.llm_provider.aget_completion(
                        messages=self.prompt_provider._get_message_payload(
                            task_prompt_name=self.kg_provider.config.kg_enrichment_settings.community_reports_prompt,
                            task_inputs={
                                "input_text": self.community_summary_prompt(
                                    entities,
                                    triples,
                                    max_summary_input_length,
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
                summary = json.loads(description)
                name = summary["name"]
                summary = summary["summary"]
                findings = summary["findings"]
                rating = summary["rating"]
                rating_explanation = summary["rating_explanation"]
                break
            except Exception as e:
                if attempt == 2:
                    raise ValueError(
                        f"Failed to generate a summary for community {community_id} at level {community_level}."
                    ) from e

        community = CommunityReport(
            community_id=community_id,
            collection_id=collection_id,
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

        await self.kg_provider.add_community_report(project_name, community, collection_id)  # type: ignore

        return {"id": community.id, "name": community.name}

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

        offset = input.message["offset"]
        limit = input.message["limit"]
        generation_config = input.message["generation_config"]
        max_summary_input_length = input.message["max_summary_input_length"]
        project_name = input.message["project_name"]
        collection_id = input.message["collection_id"]
        community_summary_jobs = []
        for community_id in range(offset, limit):
            community_summary_jobs.append(
                self.process_community(
                    project_name=project_name,
                    community_id=community_id,
                    max_summary_input_length=max_summary_input_length,
                    generation_config=generation_config,
                    collection_id=collection_id,
                )
            )

        for community_summary in asyncio.as_completed(community_summary_jobs):
            yield await community_summary
