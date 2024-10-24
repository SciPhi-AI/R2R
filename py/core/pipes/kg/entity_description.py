# pipe to extract nodes/triples etc

import asyncio
import logging
import random
import time
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    CompletionProvider,
    DatabaseProvider,
    EmbeddingProvider,
    PipeType,
    PromptProvider,
    R2RLoggingProvider,
)
from core.base.abstractions import Entity
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger()


class KGEntityDescriptionPipe(AsyncPipe):
    """
    The pipe takes input a list of nodes and extracts description from them.
    """

    class Input(AsyncPipe.Input):
        message: dict[str, Any]

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        embedding_provider: EmbeddingProvider,
        config: AsyncPipe.PipeConfig,
        pipe_logger: Optional[R2RLoggingProvider] = None,
        type: PipeType = PipeType.OTHER,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config,
        )
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider
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

        start_time = time.time()

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
                        messages=await self.prompt_provider._get_message_payload(
                            task_prompt_name=self.database_provider.config.kg_creation_settings.kg_entity_description_prompt,
                            task_inputs={
                                "entity_info": truncate_info(
                                    entity_info,
                                    max_description_input_length,
                                ),
                                "triples_txt": truncate_info(
                                    triples_txt,
                                    max_description_input_length,
                                ),
                            },
                        ),
                        generation_config=self.database_provider.config.kg_creation_settings.generation_config,
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
            await self.database_provider.upsert_embeddings(
                [
                    (
                        out_entity.name,
                        out_entity.description,
                        str(out_entity.description_embedding),
                        out_entity.extraction_ids,
                        document_id,
                    )
                ],
                "document_entity",
            )

            return out_entity.name

        offset = input.message["offset"]
        limit = input.message["limit"]
        document_id = input.message["document_id"]
        logger = input.message["logger"]

        logger.info(
            f"KGEntityDescriptionPipe: Getting entity map for document {document_id}",
        )

        entity_map = await self.database_provider.get_entity_map(
            offset, limit, document_id
        )
        total_entities = len(entity_map)

        logger.info(
            f"KGEntityDescriptionPipe: Got entity map for document {document_id}, total entities: {total_entities}, time from start: {time.time() - start_time:.2f} seconds",
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

        completed_entities = 0
        for result in asyncio.as_completed(workflows):
            if completed_entities % 100 == 0:
                logger.info(
                    f"KGEntityDescriptionPipe: Completed {completed_entities+1} of {total_entities} entities for document {document_id}",
                )
            yield await result
            completed_entities += 1

        logger.info(
            f"KGEntityDescriptionPipe: Processed {total_entities} entities for document {document_id}, time from start: {time.time() - start_time:.2f} seconds",
        )
