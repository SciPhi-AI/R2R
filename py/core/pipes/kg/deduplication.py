import json
import logging
from typing import Any, Union
from uuid import UUID

from fastapi import HTTPException

from core.base import AsyncState
from core.base.abstractions import Entity, KGEntityDeduplicationType
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


class KGEntityDeduplicationPipe(AsyncPipe):
    def __init__(
        self,
        config: AsyncPipe.PipeConfig,
        database_provider: PostgresDBProvider,
        llm_provider: Union[
            OpenAICompletionProvider, LiteLLMCompletionProvider
        ],
        embedding_provider: Union[
            LiteLLMEmbeddingProvider,
            OpenAIEmbeddingProvider,
            OllamaEmbeddingProvider,
        ],
        logging_provider: SqlitePersistentLoggingProvider,
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
                "chunk_ids",
                "document_id",
                "attributes",
            ]
            deduplication_target_keys = [
                "chunk_ids",
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
                    chunk_ids=entity["chunk_ids"],
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
            raise HTTPException(
                status_code=500,
                detail=f"KGEntityDeduplicationPipe: Error deduplicating entities: {str(e)}",
            )

    async def kg_description_entity_deduplication(
        self, collection_id: UUID, **kwargs
    ):
        from sklearn.cluster import DBSCAN

        entities = (
            await self.database_provider.get_entities(
                collection_id=collection_id,
                offset=0,
                limit=-1,
                extra_columns=["description_embedding"],
            )
        )["entities"]

        for entity in entities:
            entity.description_embedding = json.loads(
                entity.description_embedding
            )

        logger.info(
            f"KGEntityDeduplicationPipe: Got {len(entities)} entities for collection {collection_id}"
        )

        deduplication_source_keys = [
            "chunk_ids",
            "document_id",
            "attributes",
        ]
        deduplication_target_keys = [
            "chunk_ids",
            "document_ids",
            "attributes",
        ]

        deduplication_keys = list(
            zip(deduplication_source_keys, deduplication_target_keys)
        )

        embeddings = [entity.description_embedding for entity in entities]

        logger.info(
            f"KGEntityDeduplicationPipe: Running DBSCAN clustering on {len(embeddings)} embeddings"
        )
        # TODO: make eps a config, make it very strict for now
        clustering = DBSCAN(eps=0.1, min_samples=2, metric="cosine").fit(
            embeddings
        )
        labels = clustering.labels_

        # Log clustering results
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = list(labels).count(-1)
        logger.info(
            f"KGEntityDeduplicationPipe: Found {n_clusters} clusters and {n_noise} noise points"
        )

        # for all labels in the same cluster, we can deduplicate them by name
        deduplicated_entities: dict[int, list] = {}
        for id, label in enumerate(labels):
            if label != -1:
                if label not in deduplicated_entities:
                    deduplicated_entities[label] = []
                deduplicated_entities[label].append(entities[id])

        # upsert deduplcated entities in the collection_entity table
        deduplicated_entities_list = []
        for label, entities in deduplicated_entities.items():
            longest_name = ""
            descriptions = []
            aliases = set()
            for entity in entities:
                aliases.add(entity.name)
                descriptions.append(entity.description)
                if len(entity.name) > len(longest_name):
                    longest_name = entity.name

            descriptions.sort(key=len, reverse=True)
            description = "\n".join(descriptions[:5])

            # Collect all extraction IDs from entities in the cluster
            chunk_ids = set()
            document_ids = set()
            for entity in entities:
                if entity.chunk_ids:
                    chunk_ids.update(entity.chunk_ids)
                if entity.document_id:
                    document_ids.add(entity.document_id)

            chunk_ids_list = list(chunk_ids)
            document_ids_list = list(document_ids)

            deduplicated_entities_list.append(
                Entity(
                    name=longest_name,
                    description=description,
                    collection_id=collection_id,
                    chunk_ids=chunk_ids_list,
                    document_ids=document_ids_list,
                    attributes={
                        "aliases": list(aliases),
                    },
                )
            )

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

    async def kg_llm_entity_deduplication(self, collection_id: UUID, **kwargs):
        # TODO: implement LLM based entity deduplication
        raise NotImplementedError(
            "LLM entity deduplication is not implemented yet"
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

        if kg_entity_deduplication_type == KGEntityDeduplicationType.BY_NAME:
            logger.info(
                f"KGEntityDeduplicationPipe: Running named entity deduplication for collection {collection_id}"
            )
            async for result in self.kg_named_entity_deduplication(
                collection_id, **kwargs
            ):
                yield result

        elif (
            kg_entity_deduplication_type
            == KGEntityDeduplicationType.BY_DESCRIPTION
        ):
            logger.info(
                f"KGEntityDeduplicationPipe: Running description entity deduplication for collection {collection_id}"
            )
            async for result in self.kg_description_entity_deduplication(  # type: ignore
                collection_id, **kwargs
            ):
                yield result

        elif kg_entity_deduplication_type == KGEntityDeduplicationType.BY_LLM:
            logger.info(
                f"KGEntityDeduplicationPipe: Running LLM entity deduplication for collection {collection_id}"
            )
            async for result in self.kg_llm_entity_deduplication(  # type: ignore
                collection_id, **kwargs
            ):
                yield result

        else:
            raise ValueError(
                f"Invalid kg_entity_deduplication_type: {kg_entity_deduplication_type}"
            )
