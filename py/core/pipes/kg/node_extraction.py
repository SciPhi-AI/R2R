# pipe to extract nodes/triples etc

import asyncio
import logging
import random
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    CompletionProvider,
    EmbeddingProvider,
    KGProvider,
    PipeType,
    PromptProvider,
    RunLoggingSingleton,
)
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class KGNodeExtractionPipe(AsyncPipe):
    """
    The pipe takes input a list of nodes and extracts description from them.
    """

    class Input(AsyncPipe.Input):
        message: dict[str, Any]

    def __init__(
        self,
        kg_provider: KGProvider,
        config: AsyncPipe.PipeConfig,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config,
        )

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        """
        pass
        """
        pass


class KGNodeDescriptionPipe(AsyncPipe):
    """
    The pipe takes input a list of nodes and extracts description from them.
    """

    class Input(AsyncPipe.Input):
        message: dict[str, Any]

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
        config: AsyncPipe.PipeConfig,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config,
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        """
        Extracts description from the input.
        """

        summarization_content = """
            Provide a comprehensive yet concise summary of the given entity, incorporating its description and associated triples:

            Entity Info: 
            {entity_info}
            Triples: 
            {triples_txt}

            Your summary should:
            1. Clearly define the entity's core concept or purpose
            2. Highlight key relationships or attributes from the triples
            3. Integrate any relevant information from the existing description
            4. Maintain a neutral, factual tone
            5. Be approximately 2-3 sentences long

            Ensure the summary is coherent, informative, and captures the essence of the entity within the context of the provided information.
        """

        async def process_entity(
            entities_info: list[dict[str, Any]],
            triples: list[dict[str, Any]],
            max_description_input_length: int,
        ):

            entity_info = [
                f"{entity['name']}, {entity['category']}, {entity['description']}"
                for entity in entities_info
            ]
            triples_txt = [
                f"{i+1}: {triple['subject']}, {triple['object']}, {triple['predicate']} - Summary: {triple['description']}"
                for i, triple in enumerate(triples)
            ]

            # truncate the descriptions to the max_description_input_length
            # randomly shuffle the triples
            # randomly select elements from the triples_txt until the length is less than max_description_input_length
            random.shuffle(triples_txt)
            truncated_triples_txt = ""
            current_length = 0
            for triple in triples_txt:
                if current_length + len(triple) > max_description_input_length:
                    break
                truncated_triples_txt += triple + "\n"
                current_length += len(triple)

            out_entity = {"name": entities_info[0]["name"]}
            out_entity["description"] = (
                (
                    await self.llm_provider.aget_completion(
                        messages=[
                            {
                                "role": "user",
                                "content": summarization_content.format(
                                    entity_info=entity_info,
                                    triples_txt=truncated_triples_txt,
                                ),
                            }
                        ],
                        generation_config=self.kg_provider.config.kg_enrichment_settings.generation_config,
                    )
                )
                .choices[0]
                .message.content
            )

            # will do more requests, but it is simpler
            out_entity["description_embedding"] = (
                await self.embedding_provider.async_get_embeddings(
                    [out_entity["description"]]
                )
            )[0]

            return out_entity

        max_description_input_length = input.message[
            "max_description_input_length"
        ]

        offset = input.message["offset"]
        limit = input.message["limit"]
        project_name = input.message["project_name"]

        entity_map = await self.kg_provider.get_entity_map(
            offset, limit, project_name
        )

        for entity_name, entity_info in entity_map.items():
            try:
                logger.info(f"Processing entity {entity_name}")
                processed_entity = await process_entity(
                    entity_info["entities"],
                    entity_info["triples"],
                    max_description_input_length,
                )

                await self.kg_provider.upsert_embeddings(
                    [
                        (
                            processed_entity["name"],
                            processed_entity["description"],
                            str(processed_entity["description_embedding"]),
                        )
                    ],
                    "entity_embeddings",
                    project_name,
                )
                logger.info(f"Processed entity {entity_name}")

                yield entity_name
            except Exception as e:
                logger.error(f"Error processing entity {entity_name}: {e}")
                # import pdb; pdb.set_trace()
