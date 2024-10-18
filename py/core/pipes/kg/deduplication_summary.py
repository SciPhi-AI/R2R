import asyncio
import logging
from core.base.pipes import AsyncPipe
from core.base.providers import KGProvider, PromptProvider, CompletionProvider, EmbeddingProvider
from typing import Optional

from core.base.logging import R2RLoggingProvider
from core.base.pipes import AsyncPipe, PipeType

logger = logging.getLogger(__name__)

class KGEntityDeduplicationSummaryPipe(AsyncPipe):
    def __init__(self, kg_provider: KGProvider, prompt_provider: PromptProvider, llm_provider: CompletionProvider, embedding_provider: EmbeddingProvider, config: AsyncPipe.PipeConfig, pipe_logger: Optional[R2RLoggingProvider] = None, type: PipeType = PipeType.OTHER, **kwargs):
        super().__init__(pipe_logger=pipe_logger, type=type, config=config, **kwargs)
        self.kg_provider = kg_provider
        self.prompt_provider = prompt_provider
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def _merge_entity_descriptions_llm_prompt(self, entity_name: str, entity_descriptions: list[str]) -> str:

        # find the index until the length is less than 1024
        index = 0
        while index < len(entity_descriptions):
            if len(entity_descriptions[index]) + len(description) > self.kg_provider.config.kg_entity_deduplication_settings.max_description_input_length:
                break
            index += 1

        description = (
            await self.llm_provider.aget_completion(
                messages= await self.prompt_provider._get_message_payload(
                    task_prompt_name=self.kg_provider.config.kg_entity_deduplication_settings.kg_entity_deduplication_prompt,
                    task_inputs={
                        "entity_name": (
                            entity_name,
                        ),
                        "entity_descriptions": (
                            "\n".join(entity_descriptions[:index]),
                        ),
                    },
                ),
                generation_config=self.kg_provider.config.kg_entity_deduplication_settings.generation_config,
            )
        )

        # get the $$description$$
        try:
            description = description.choices[0].message.content
            description = description.split("$$")[1]
        except: 
            logger.error(f"Failed to generate a summary for entity {entity_name}.")

        return {
            "name": entity_name,        
            "description": description
        }

    async def _merge_entity_descriptions(self, entity_name: str, entity_descriptions: list[str]) -> str:
        
        # TODO: Expose this as a hyperparameter
        if len(entity_descriptions) <= 5:
            return "\n".join(entity_descriptions)
        else:
            return await self._merge_entity_descriptions_llm_prompt(entity_name, entity_descriptions)

    async def _prepare_and_upsert_entities(self, entities_batch: list[dict], collection_id: str) -> list[dict]:

        embeddings = await self.embedding_provider.get_embeddings([description["description"] for description in entities_batch])

        for i, entity in enumerate(entities_batch):
            entity["description_embedding"] = embeddings[i]
            entity["collection_id"] = collection_id

        return await self.kg_provider.add_entities(entities_batch, entity_table_name="entity_deduplicated", conflict_columns=["name", "collection_id"])

    async def _run_logic(self, **kwargs) -> dict:

        collection_id = kwargs["collection_id"]
        offset = kwargs["offset"]
        limit = kwargs["limit"]

        entities = await self.kg_provider.get_entities(collection_id, offset, limit, entity_table_name="entity_deduplicated")

        entity_names = [entity["name"] for entity in entities]

        entity_descriptions = await self.kg_provider.get_entities(collection_id, offset, limit, entity_names=entity_names, entity_table_name="entity_embedding")
        
        entity_descriptions_dict = {}
        for entity_description in entity_descriptions:        
            if not entity_description["name"] in entity_descriptions_dict:
                entity_descriptions_dict[entity_description["name"]] = []
            entity_descriptions_dict[entity_description["name"]].append(entity_description["description"])

        tasks = []
        for entity in entities:
            tasks.append(self._merge_entity_descriptions(entity["name"], entity_descriptions_dict[entity["name"]]))

        entities_batch = []
        for async_result in asyncio.as_completed(tasks):
            result = await async_result
            entities_batch.append(result)

            if len(entities_batch) == self.kg_provider.config.kg_entity_deduplication_settings.batch_size:
                await self._prepare_and_upsert_entities(entities_batch, collection_id)
                entities_batch = []

        if entities_batch:
            await self._prepare_and_upsert_entities(entities_batch, collection_id)

        return {
            "result": f"successfully deduplicated {len(entities)} entities for collection {collection_id}",
            "num_entities": len(entities)
        }