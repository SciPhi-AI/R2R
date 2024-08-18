# pipe to extract nodes/triples etc

import asyncio
import logging
import uuid
from typing import Any, AsyncGenerator, Optional, Union

from r2r.base import (
    AsyncState,
    CompletionProvider,
    EmbeddingProvider,
    KGExtraction,
    KGProvider,
    PipeType,
    PromptProvider,
    R2RDocumentProcessingError,
    RunLoggingSingleton,
)
from r2r.base.abstractions.graph import Entity, Triple
from r2r.base.pipes.base_pipe import AsyncPipe
from r2r.base.providers.llm import GenerationConfig

logger = logging.getLogger(__name__)


class KGNodeExtractionPipe(AsyncPipe):
    """
    The pipe takes input a list of documents (optional) and extracts nodes and triples from them.
    """

    class Input(AsyncPipe.Input):
        message: Any

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config
            or AsyncPipe.PipeConfig(name="kg_node_extraction_pipe"),
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: uuid.UUID,
        *args,
        **kwargs,
    ) -> AsyncGenerator[Any, None]:

        nodes = self.kg_provider.get_entity_map()

        for node_value, node_info in nodes.items():
            for entity in node_info["entities"]:
                yield entity, node_info[
                    "triples"
                ]  # the entity and its associated triples


class KGNodeDescriptionPipe(AsyncPipe):
    """
    The pipe takes input a list of nodes and extracts description from them.
    """

    class Input(AsyncPipe.Input):
        message: AsyncGenerator[tuple[Entity, list[Triple]], None]

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config
            or AsyncPipe.PipeConfig(name="kg_node_description_pipe"),
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: uuid.UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        """
        Extracts description from the input.
        """

        # summarization_content  = """

        #     You are given the following entity and its associated triples:
        #     Entity: {entity_info}
        #     Triples: {triples_txt}
        #     Your tasks:

        #     Entity Description:
        #     Provide a concise description of the entity based on the given information and triples.

        #     Entity Analysis:
        #     a) Determine if this entity represents a single concept or a combination of multiple entities.
        #     b) If it's a combination, list the separate entities that make up this composite entity.
        #     c) Map each separate entity to the relationship(s) it came from in the original triples.
        #     d) Suggest more appropriate names for each separate entity if applicable.

        #     Formatted Output:
        #     For each entity (original or separate), provide the following formatted output:
        #     ("entity"$$$$<entity_name>$$$$<entity_type>$$$$<entity_description>$$$$<associated_triples>)

        #     Where:
        #     <entity_name>: The name of the entity (original or improved)
        #     <entity_type>: The type or category of the entity
        #     <entity_description>: A concise description of the entity
        #     <associated_triples>: List of triples associated with this specific entity

        #     Explanation:
        #     Briefly explain your reasoning for separating entities (if applicable) and any name changes you suggested.

        #     Please ensure your response is clear, concise, and follows the requested format.
        # """

        summarization_content = """
            Provide a comprehensive yet concise summary of the given entity, incorporating its description and associated triples:

            Entity: {entity_info}
            Description: {description}
            Triples: {triples_txt}

            Your summary should:
            1. Clearly define the entity's core concept or purpose
            2. Highlight key relationships or attributes from the triples
            3. Integrate any relevant information from the existing description
            4. Maintain a neutral, factual tone
            5. Be approximately 2-3 sentences long

            Ensure the summary is coherent, informative, and captures the essence of the entity within the context of the provided information.
        """

        async def process_entity(entity, triples):

            # if embedding is present in the entity, just return it
            # in the future disable this to override and recompute the descriptions for all entities
            if entity.description_embedding and entity.name_embedding:
                return entity

            entity_info = f"{entity.name}, {entity.description}"
            triples_txt = "\n".join(
                [
                    f"{i+1}: {triple.subject}, {triple.object}, {triple.predicate} - Summary: {triple.description}"
                    for i, triple in enumerate(triples)
                ]
            )

            messages = [
                {
                    "role": "user",
                    "content": summarization_content.format(
                        entity_info=entity_info,
                        description=entity.description,
                        triples_txt=triples_txt,
                    ),
                }
            ]

            out_entity = self.kg_provider.retrieve_cache(
                "entities_with_description", f"{entity.name}_{entity.category}"
            )
            if out_entity:
                logger.info(f"Hit cache for entity {entity.name}")
            else:
                completion = await self.llm_provider.aget_completion(
                    messages, GenerationConfig(model="gpt-4o-mini")
                )
                entity.description = completion.choices[0].message.content

                # embedding
                description_embedding = (
                    await self.embedding_provider.async_get_embeddings(
                        [entity.description]
                    )
                )
                entity.description_embedding = description_embedding[0]

                # name embedding
                name_embedding = (
                    await self.embedding_provider.async_get_embeddings(
                        [entity.name]
                    )
                )
                entity.name_embedding = name_embedding[0]

                out_entity = entity

            return out_entity

        tasks = []
        count = 0
        async for entity, triples in input.message:
            tasks.append(asyncio.create_task(process_entity(entity, triples)))
            count += 1
            if count == 4:
                break

        processed_entities = await asyncio.gather(*tasks)

        # upsert to the database
        self.kg_provider.upsert_entities(
            processed_entities, with_embeddings=True
        )

        for entity in processed_entities:
            yield entity
