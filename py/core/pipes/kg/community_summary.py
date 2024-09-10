import json
import logging
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    Community,
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
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        config: Optional[AsyncPipe.PipeConfig] = None,
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
        prompt: str,
        entities: list[Entity],
        triples: list[Triple],
        max_summary_input_length: int,
    ):
        """
        Preparing the list of entities and triples to be summarized and created into a community summary.
        """
        entities_info = "\n".join(
            [f"{entity.name}, {entity.description}" for entity in entities]
        )

        triples_info = "\n".join(
            [
                f"{triple.subject}, {triple.object}, {triple.predicate}, {triple.description}"
                for triple in triples
            ]
        )

        prompt = prompt.format(entities=entities_info, triples=triples_info)

        if len(prompt) > max_summary_input_length:
            logger.info(
                f"Community summary prompt was created of length {len(prompt)}, trimming to {max_summary_input_length} characters."
            )
            prompt = prompt[:max_summary_input_length]

        return prompt

    async def process_community(
        self,
        level: int,
        community_id: str,
        max_summary_input_length: int,
        generation_config: GenerationConfig,
    ) -> dict:
        """
        Process a community by summarizing it and creating a summary embedding and storing it to a neo4j database.

        Input:
        - level: The level of the hierarchy.
        - community_id: The ID of the community to process.

        Output:
        - A dictionary with the community id and the title of the community.
        - Output format: {"id": community_id, "title": title}
        """

        input_text = """

            Entities:
            {entities}

            Triples:
            {triples}

        """

        logger.info(
            f"Processing community {community_id} at level {level} with max summary input length {max_summary_input_length}."
        )

        entities, triples = (
            self.kg_provider.get_community_entities_and_triples(
                level=level, community_id=community_id
            )
        )

        if entities == [] or triples == []:
            return None

        description = (
            (
                await self.llm_provider.aget_completion(
                    messages=self.prompt_provider._get_message_payload(
                        task_prompt_name="graphrag_community_reports",
                        task_inputs={
                            "input_text": self.community_summary_prompt(
                                input_text,
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

        community = Community(
            id=str(community_id),
            level=str(level),
            summary=description,
            summary_embedding=await self.embedding_provider.async_get_embedding(
                description
            ),
        )

        self.kg_provider.upsert_communities([community])

        try:
            summary = json.loads(community.summary)
        except:
            summary = {"title": ""}

        return {"id": community.id, "title": summary["title"]}

    async def _run_logic(
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

        community_id = input.message["community_id"]
        level = input.message["level"]
        generation_config = input.message["generation_config"]
        max_summary_input_length = input.message["max_summary_input_length"]

        community_summary = await self.process_community(
            level=level,
            community_id=community_id,
            max_summary_input_length=max_summary_input_length,
            generation_config=generation_config,
        )

        yield community_summary
