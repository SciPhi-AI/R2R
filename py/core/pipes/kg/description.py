# pipe to extract nodes/relationships etc

import asyncio
import logging
import random
import time
from typing import Any, AsyncGenerator
from uuid import UUID

from core.base import AsyncState, CompletionProvider, EmbeddingProvider
from core.base.pipes.base_pipe import AsyncPipe

from ...database.postgres import PostgresDatabaseProvider

logger = logging.getLogger()


class GraphDescriptionPipe(AsyncPipe):
    """
    The pipe takes input a list of nodes and extracts description from them.
    """

    class Input(AsyncPipe.Input):
        message: dict[str, Any]

    def __init__(
        self,
        database_provider: PostgresDatabaseProvider,
        llm_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
        config: AsyncPipe.PipeConfig,
        *args,
        **kwargs,
    ):
        super().__init__(
            config=config,
        )
        self.database_provider = database_provider
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
            entities,
            relationships,
            max_description_input_length,
            document_id: UUID,
        ):
            response = await self.database_provider.documents_handler.get_documents_overview(  # type: ignore
                offset=0,
                limit=1,
                filter_document_ids=[document_id],
            )
            document_summary = (
                response["results"][0].summary if response["results"] else None
            )

            entity_info = [
                f"{entity.name}, {entity.description}" for entity in entities
            ]

            relationships_txt = [
                f"{i+1}: {relationship.subject}, {relationship.object}, {relationship.predicate} - Summary: {relationship.description}"
                for i, relationship in enumerate(relationships)
            ]

            # potentially slow at scale, but set to avoid duplicates
            unique_chunk_ids = set()
            for entity in entities:
                for chunk_id in entity.chunk_ids:
                    unique_chunk_ids.add(chunk_id)

            out_entity = entities[0]
            if not out_entity.description:
                out_entity.description = (
                    (
                        await self.llm_provider.aget_completion(
                            messages=await self.database_provider.prompts_handler.get_message_payload(
                                task_prompt_name=self.database_provider.config.graph_creation_settings.graph_entity_description_prompt,
                                task_inputs={
                                    "document_summary": document_summary,
                                    "entity_info": truncate_info(
                                        entity_info,
                                        max_description_input_length,
                                    ),
                                    "relationships_txt": truncate_info(
                                        relationships_txt,
                                        max_description_input_length,
                                    ),
                                },
                            ),
                            generation_config=self.database_provider.config.graph_creation_settings.generation_config,
                        )
                    )
                    .choices[0]
                    .message.content
                )

                if not out_entity.description:
                    logger.error(
                        f"No description for entity {out_entity.name}"
                    )
                    return out_entity.name

                out_entity.description_embedding = (
                    await self.embedding_provider.async_get_embeddings(
                        [out_entity.description]
                    )
                )[0]

                # upsert the entity and its embedding
                await self.database_provider.graphs_handler.add_entities(
                    [out_entity],
                    table_name="documents_entities",
                )

            return out_entity.name

        offset = input.message["offset"]
        limit = input.message["limit"]
        document_id = input.message["document_id"]
        logger = input.message["logger"]

        logger.info(
            f"GraphDescriptionPipe: Getting entity map for document {document_id}",
        )

        entity_map = (
            await self.database_provider.graphs_handler.get_entity_map(
                offset, limit, document_id
            )
        )
        total_entities = len(entity_map)

        logger.info(
            f"GraphDescriptionPipe: Got entity map for document {document_id}, total entities: {total_entities}, time from start: {time.time() - start_time:.2f} seconds",
        )

        workflows = []

        for _, (entity_name, entity_info) in enumerate(entity_map.items()):
            try:
                workflows.append(
                    process_entity(
                        entities=entity_info["entities"],
                        relationships=entity_info["relationships"],
                        max_description_input_length=input.message[
                            "max_description_input_length"
                        ],
                        document_id=document_id,
                    )
                )
            except Exception as e:
                logger.error(f"Error processing entity {entity_name}: {e}")

        completed_entities = 0
        for result in asyncio.as_completed(workflows):
            if completed_entities % 100 == 0:
                logger.info(
                    f"GraphDescriptionPipe: Completed {completed_entities+1} of {total_entities} entities for document {document_id}",
                )
            yield await result
            completed_entities += 1

        logger.info(
            f"GraphDescriptionPipe: Processed {total_entities} entities for document {document_id}, time from start: {time.time() - start_time:.2f} seconds",
        )
