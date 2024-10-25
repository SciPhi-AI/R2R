import logging
from typing import Any, Optional, Union
from uuid import UUID

from core.base import AsyncState, R2RException
from core.base.abstractions import Entity, KGEntityDeduplicationType
from core.base.pipes import AsyncPipe
from core.providers import (
    LiteLLMCompletionProvider,
    LiteLLMEmbeddingProvider,
    OpenAICompletionProvider,
    OpenAIEmbeddingProvider,
    PostgresDBProvider,
)
from core.providers.logging.r2r_logging import R2RLoggingProvider

logger = logging.getLogger()


class KGEntityDeduplicationPipe(AsyncPipe):
    def __init__(
        self,
        config: AsyncPipe.PipeConfig,
        database_provider: PostgresDBProvider,
        llm_provider: Union[
            OpenAICompletionProvider, LiteLLMCompletionProvider
        ],
        embedding_provider: Union[
            LiteLLMEmbeddingProvider, OpenAIEmbeddingProvider
        ],
        logging_provider: Optional[R2RLoggingProvider] = None,
        **kwargs,
    ):
        super().__init__(
            logging_provider=logging_provider,
            config=config
            or AsyncPipe.PipeConfig(name="kg_entity_deduplication_pipe"),
        )
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def kg_named_entity_deduplication(
        self, collection_id: UUID, **kwargs
    ):
        try:
            entity_count = await self.database_provider.get_entity_count(
                collection_id=collection_id, distinct=True
            )

            logger.info(
                f"KGEntityDeduplicationPipe: Getting entities for collection {collection_id}"
            )
            logger.info(
                f"KGEntityDeduplicationPipe: Entity count: {entity_count}"
            )

            entities = (
                await self.database_provider.get_entities(
                    collection_id=collection_id, offset=0, limit=-1
                )
            )["entities"]

            logger.info(
                f"KGEntityDeduplicationPipe: Got {len(entities)} entities for collection {collection_id}"
            )

            # deduplicate entities by name
            deduplicated_entities: dict[str, dict[str, list[str]]] = {}
            deduplication_source_keys = [
                "extraction_ids",
                "document_id",
                "attributes",
            ]
            deduplication_target_keys = [
                "extraction_ids",
                "document_ids",
                "attributes",
            ]
            deduplication_keys = list(
                zip(deduplication_source_keys, deduplication_target_keys)
            )
            for entity in entities:
                if entity.name not in deduplicated_entities:
                    deduplicated_entities[entity.name] = {
                        target_key: [] for _, target_key in deduplication_keys
                    }
                for source_key, target_key in deduplication_keys:
                    value = getattr(entity, source_key)
                    if isinstance(value, list):
                        deduplicated_entities[entity.name][target_key].extend(
                            value
                        )
                    else:
                        deduplicated_entities[entity.name][target_key].append(
                            value
                        )

            logger.info(
                f"KGEntityDeduplicationPipe: Deduplicated {len(deduplicated_entities)} entities"
            )

            # upsert deduplcated entities in the collection_entity table
            deduplicated_entities_list = [
                Entity(
                    name=name,
                    collection_id=collection_id,
                    extraction_ids=entity["extraction_ids"],
                    document_ids=entity["document_ids"],
                    attributes={},
                )
                for name, entity in deduplicated_entities.items()
            ]

            logger.info(
                f"KGEntityDeduplicationPipe: Upserting {len(deduplicated_entities_list)} deduplicated entities for collection {collection_id}"
            )
            await self.database_provider.add_entities(
                deduplicated_entities_list,
                table_name="collection_entity",
                conflict_columns=["name", "collection_id", "attributes"],
            )

            yield {
                "result": f"successfully deduplicated {len(entities)} entities to {len(deduplicated_entities)} entities for collection {collection_id}",
                "num_entities": len(deduplicated_entities),
            }
        except Exception as e:
            logger.error(
                f"KGEntityDeduplicationPipe: Error in entity deduplication: {str(e)}"
            )
            raise R2RException(
                message=f"KGEntityDeduplicationPipe: Error deduplicating entities: {str(e)}",
                status_code=500,
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

        collection_id = input.message["collection_id"]

        kg_entity_deduplication_type = input.message[
            "kg_entity_deduplication_type"
        ]

        if kg_entity_deduplication_type != KGEntityDeduplicationType.BY_NAME:
            raise NotImplementedError(
                f"KGEntityDeduplicationPipe: Deduplication type {kg_entity_deduplication_type} not implemented"
            )
        async for result in self.kg_named_entity_deduplication(
            collection_id, **kwargs
        ):
            yield result
