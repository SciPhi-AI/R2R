import asyncio
import logging
from typing import Any, Optional, Union
from uuid import UUID

from core.base import AsyncState
from core.base.abstractions import Entity, GenerationConfig
from core.base.pipes import AsyncPipe
from core.providers import (
    LiteLLMCompletionProvider,
    LiteLLMEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAICompletionProvider,
    OpenAIEmbeddingProvider,
    PostgresDBProvider,
)
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider

logger = logging.getLogger()


class KGEntityDeduplicationSummaryPipe(AsyncPipe[Any]):

    class Input(AsyncPipe.Input):
        message: dict

    def __init__(
        self,
        database_provider: PostgresDBProvider,
        llm_provider: Union[
            LiteLLMCompletionProvider, OpenAICompletionProvider
        ],
        embedding_provider: Union[
            LiteLLMEmbeddingProvider,
            OpenAIEmbeddingProvider,
            OllamaEmbeddingProvider,
        ],
        config: AsyncPipe.PipeConfig,
        logging_provider: SqlitePersistentLoggingProvider,
        **kwargs,
    ):
        super().__init__(
            logging_provider=logging_provider, config=config, **kwargs
        )
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def _merge_entity_descriptions_llm_prompt(
        self,
        entity_name: str,
        entity_descriptions: list[str],
        generation_config: GenerationConfig,
    ) -> Entity:

        # find the index until the length is less than 1024
        index = 0
        description_length = 0
        while index < len(entity_descriptions) and not (
            len(entity_descriptions[index]) + description_length
            > self.database_provider.config.graph_entity_deduplication_settings.max_description_input_length
        ):
            description_length += len(entity_descriptions[index])
            index += 1

        completion = await self.llm_provider.aget_completion(
            messages=await self.database_provider.prompt_handler.get_message_payload(
                task_prompt_name=self.database_provider.config.graph_entity_deduplication_settings.graph_entity_deduplication_prompt,
                task_inputs={
                    "entity_name": entity_name,
                    "entity_descriptions": "\n".join(
                        entity_descriptions[:index]
                    ),
                },
            ),
            generation_config=GenerationConfig(**generation_config),  # type: ignore
        )

        # get the $$description$$
        try:
            description = completion.choices[0].message.content or ""
            description = description.split("$$")[1]
        except:
            logger.error(
                f"Failed to generate a summary for entity {entity_name}."
            )

        return Entity(name=entity_name, description=description)

    async def _merge_entity_descriptions(
        self,
        entity_name: str,
        entity_descriptions: list[str],
        generation_config: GenerationConfig,
    ) -> Entity:

        # TODO: Expose this as a hyperparameter
        if len(entity_descriptions) <= 5:
            return Entity(
                name=entity_name, description="\n".join(entity_descriptions)
            )
        else:
            return await self._merge_entity_descriptions_llm_prompt(
                entity_name, entity_descriptions, generation_config
            )

    async def _prepare_and_upsert_entities(
        self, entities_batch: list[Entity], graph_id: UUID
    ) -> Any:

        embeddings = await self.embedding_provider.async_get_embeddings(
            [entity.description or "" for entity in entities_batch]
        )

        for i, entity in enumerate(entities_batch):
            entity.description_embedding = str(embeddings[i])  # type: ignore
            entity.graph_id = graph_id

        logger.info(
            f"Upserting {len(entities_batch)} entities for graph {graph_id}"
        )

        await self.database_provider.graph_handler.update_entity_descriptions(
            entities_batch
        )

        logger.info(
            f"Upserted {len(entities_batch)} entities for graph {graph_id}"
        )

        for entity in entities_batch:
            yield entity

    async def _get_entities(
        self,
        graph_id: Optional[UUID],
        collection_id: Optional[UUID],
        offset: int,
        limit: int,
        level,
    ):

        if graph_id is not None:
            return await self.database_provider.graph_handler.entities.get(
                parent_id=graph_id,
                offset=offset,
                limit=limit,
                level=level,
            )

        elif collection_id is not None:
            return await self.database_provider.graph_handler.get_entities(
                parent_id=collection_id,
                offset=offset,
                limit=limit,
            )

        else:
            raise ValueError(
                "Either graph_id or collection_id must be provided"
            )

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ):
        # TODO: figure out why the return type AsyncGenerator[dict, None] is not working

        graph_id = input.message.get("graph_id", None)
        collection_id = input.message.get("collection_id", None)
        offset = input.message["offset"]
        limit = input.message["limit"]
        graph_entity_deduplication_type = input.message[
            "graph_entity_deduplication_type"
        ]
        graph_entity_deduplication_prompt = input.message[
            "graph_entity_deduplication_prompt"
        ]
        generation_config = input.message["generation_config"]

        logger.info(
            f"Running kg_entity_deduplication_summary for graph {graph_id} with settings graph_entity_deduplication_type: {graph_entity_deduplication_type}, graph_entity_deduplication_prompt: {graph_entity_deduplication_prompt}, generation_config: {generation_config}"
        )

        entities = await self._get_entities(
            graph_id,
            collection_id,
            offset,
            limit,  # type: ignore
        )

        entity_names = [entity.name for entity in entities]

        entity_descriptions = (
            await self.database_provider.graph_handler.get_entities(
                parent_id=collection_id,
                entity_names=entity_names,
                offset=offset,
                limit=limit,
            )
        )["entities"]

        entity_descriptions_dict: dict[str, list[str]] = {}
        for entity_description in entity_descriptions:
            if entity_description.name not in entity_descriptions_dict:
                entity_descriptions_dict[entity_description.name] = []
            entity_descriptions_dict[entity_description.name].append(
                entity_description.description
            )

        logger.info(
            f"Retrieved {len(entity_descriptions)} entity descriptions for graph {graph_id}"
        )

        tasks = []
        entities_batch = []
        for entity in entities:
            tasks.append(
                self._merge_entity_descriptions(
                    entity.name,
                    entity_descriptions_dict[entity.name],
                    generation_config,
                )
            )

            if len(tasks) == 32:
                entities_batch = await asyncio.gather(*tasks)
                # prepare and upsert entities

                async for result in self._prepare_and_upsert_entities(
                    entities_batch, graph_id
                ):
                    yield result

                tasks = []

        if tasks:

            entities_batch = await asyncio.gather(*tasks)
            for entity in entities_batch:
                yield entity

            # prepare and upsert entities
            async for result in self._prepare_and_upsert_entities(
                entities_batch, graph_id
            ):
                yield result
