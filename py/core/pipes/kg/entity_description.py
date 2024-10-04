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
    RunLoggingSingleton,
)
from core.base.abstractions import Entity
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class KGEntityDescriptionPipe(AsyncPipe):
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

        # TODO - Move this to a .yaml file and load it as we do in triples extraction
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

        def truncate_info(info_list, max_length):
            random.shuffle(info_list)
            truncated_info = ""
            current_length = 0
            for info in info_list:
                if current_length + len(info) > max_length:
                    break
                truncated_info += info + "\n"
                current_length += len(info)

            return truncated_info

        async def process_entity(
            entities, triples, max_description_input_length, document_id
        ):

            entity_info = [
                f"{entity.name}, {entity.description}" for entity in entities
            ]

            triples_txt = [
                f"{i+1}: {triple.subject}, {triple.object}, {triple.predicate} - Summary: {triple.description}"
                for i, triple in enumerate(triples)
            ]

            # potentially slow at scale, but set to avoid duplicates
            unique_extraction_ids = set()
            for entity in entities:
                for extraction_id in entity.extraction_ids:
                    unique_extraction_ids.add(extraction_id)

            out_entity = Entity(
                name=entities[0].name,
                extraction_ids=list(unique_extraction_ids),
                document_ids=[document_id],
            )

            out_entity.description = (
                (
                    await self.llm_provider.aget_completion(
                        messages=[
                            {
                                "role": "user",
                                "content": summarization_content.format(
                                    entity_info=truncate_info(
                                        entity_info,
                                        max_description_input_length,
                                    ),
                                    triples_txt=truncate_info(
                                        triples_txt,
                                        max_description_input_length,
                                    ),
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
            out_entity.description_embedding = (
                await self.embedding_provider.async_get_embeddings(
                    [out_entity.description]
                )
            )[0]

            # upsert the entity and its embedding
            await self.kg_provider.upsert_embeddings(
                [
                    (
                        out_entity.name,
                        out_entity.description,
                        str(out_entity.description_embedding),
                        out_entity.extraction_ids,
                        document_id,
                    )
                ],
                "entity_embedding",
            )

            return out_entity.name

        offset = input.message["offset"]
        limit = input.message["limit"]
        document_id = input.message["document_id"]
        entity_map = await self.kg_provider.get_entity_map(
            offset, limit, document_id
        )

        total_entities = len(entity_map)
        logger.info(
            f"Processing {total_entities} entities for document {document_id}"
        )

        workflows = []
        for i, (entity_name, entity_info) in enumerate(entity_map.items()):
            try:
                workflows.append(
                    process_entity(
                        entity_info["entities"],
                        entity_info["triples"],
                        input.message["max_description_input_length"],
                        document_id,
                    )
                )
            except Exception as e:
                logger.error(f"Error processing entity {entity_name}: {e}")

        for result in asyncio.as_completed(workflows):
            yield await result

        logger.info(
            f"Processed {total_entities} entities for document {document_id}"
        )
