import asyncio
import json
import logging
import re
import time
from typing import Any, AsyncGenerator, Optional, Union

from core.base import (
    AsyncState,
    CompletionProvider,
    DocumentChunk,
    Entity,
    GenerationConfig,
    KGExtraction,
    R2RDocumentProcessingError,
    R2RException,
    Relationship,
)
from core.base.pipes.base_pipe import AsyncPipe
from core.providers.database import PostgresDBProvider
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider

logger = logging.getLogger()


MIN_VALID_KG_EXTRACTION_RESPONSE_LENGTH = 128


class ClientError(Exception):
    """Base class for client connection errors."""

    pass


class KGExtractionPipe(AsyncPipe[dict]):
    """
    Extracts knowledge graph information from document extractions.
    """

    # TODO - Apply correct type hints to storage messages
    class Input(AsyncPipe.Input):
        message: dict

    def __init__(
        self,
        database_provider: PostgresDBProvider,
        llm_provider: CompletionProvider,
        config: AsyncPipe.PipeConfig,
        logging_provider: SqlitePersistentLoggingProvider,
        kg_batch_size: int = 1,
        graph_rag: bool = True,
        id_prefix: str = "demo",
        *args,
        **kwargs,
    ):
        super().__init__(
            logging_provider=logging_provider,
            config=config
            or AsyncPipe.PipeConfig(
                name="default_kg_relationships_extraction_pipe"
            ),
        )
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.kg_batch_size = kg_batch_size
        self.id_prefix = id_prefix
        self.pipe_run_info = None
        self.graph_rag = graph_rag

    async def extract_kg(
        self,
        extractions: list[DocumentChunk],
        generation_config: GenerationConfig,
        max_knowledge_relationships: int,
        entity_types: list[str],
        relation_types: list[str],
        retries: int = 5,
        delay: int = 2,
        task_id: Optional[int] = None,
        total_tasks: Optional[int] = None,
    ) -> KGExtraction:
        """
        Extracts NER relationships from a extraction with retries.
        """

        # combine all extractions into a single string
        combined_extraction: str = " ".join([extraction.data for extraction in extractions])  # type: ignore

        messages = await self.database_provider.prompt_handler.get_message_payload(
            task_prompt_name=self.database_provider.config.graph_creation_settings.graphrag_relationships_extraction_few_shot,
            task_inputs={
                "input": combined_extraction,
                "max_knowledge_relationships": max_knowledge_relationships,
                "entity_types": "\n".join(entity_types),
                "relation_types": "\n".join(relation_types),
            },
        )

        for attempt in range(retries):
            try:
                response = await self.llm_provider.aget_completion(
                    messages,
                    generation_config=generation_config,
                )

                kg_extraction = response.choices[0].message.content

                if not kg_extraction:
                    raise R2RException(
                        "No knowledge graph extraction found in the response string, the selected LLM likely failed to format it's response correctly.",
                        400,
                    )

                entity_pattern = (
                    r'\("entity"\${4}([^$]+)\${4}([^$]+)\${4}([^$]+)\)'
                )
                relationship_pattern = r'\("relationship"\${4}([^$]+)\${4}([^$]+)\${4}([^$]+)\${4}([^$]+)\${4}(\d+(?:\.\d+)?)\)'

                def parse_fn(response_str: str) -> Any:
                    entities = re.findall(entity_pattern, response_str)

                    if (
                        len(kg_extraction)
                        > MIN_VALID_KG_EXTRACTION_RESPONSE_LENGTH
                        and len(entities) == 0
                    ):
                        raise R2RException(
                            f"No entities found in the response string, the selected LLM likely failed to format it's response correctly. {response_str}",
                            400,
                        )

                    relationships = re.findall(
                        relationship_pattern, response_str
                    )

                    entities_arr = []
                    for entity in entities:
                        entity_value = entity[0]
                        entity_category = entity[1]
                        entity_description = entity[2]
                        entities_arr.append(
                            Entity(
                                category=entity_category,
                                description=entity_description,
                                name=entity_value,
                                parent_id=extractions[0].document_id,
                                chunk_ids=[
                                    extraction.id for extraction in extractions
                                ],
                                attributes={},
                            )
                        )

                    relations_arr = []
                    for relationship in relationships:
                        subject = relationship[0]
                        object = relationship[1]
                        predicate = relationship[2]
                        description = relationship[3]
                        weight = float(relationship[4])

                        # check if subject and object are in entities_dict
                        relations_arr.append(
                            Relationship(
                                subject=subject,
                                predicate=predicate,
                                object=object,
                                description=description,
                                weight=weight,
                                parent_id=extractions[0].document_id,
                                chunk_ids=[
                                    extraction.id for extraction in extractions
                                ],
                                attributes={},
                            )
                        )

                    return entities_arr, relations_arr

                entities, relationships = parse_fn(kg_extraction)
                return KGExtraction(
                    entities=entities,
                    relationships=relationships,
                )

            except (
                ClientError,
                json.JSONDecodeError,
                KeyError,
                IndexError,
                R2RException,
            ) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Failed after retries with for chunk {extractions[0].id} of document {extractions[0].document_id}: {e}"
                    )
                    # raise e # you should raise an error.
        # add metadata to entities and relationships

        logger.info(
            f"KGExtractionPipe: Completed task number {task_id} of {total_tasks} for document {extractions[0].document_id}",
        )

        return KGExtraction(
            entities=[],
            relationships=[],
        )

    async def _run_logic(  # type: ignore
        self,
        input: Input,
        state: AsyncState,
        run_id: Any,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[KGExtraction, R2RDocumentProcessingError], None]:

        start_time = time.time()

        document_id = input.message["document_id"]
        generation_config = input.message["generation_config"]
        chunk_merge_count = input.message["chunk_merge_count"]
        max_knowledge_relationships = input.message[
            "max_knowledge_relationships"
        ]
        entity_types = input.message["entity_types"]
        relation_types = input.message["relation_types"]

        filter_out_existing_chunks = input.message.get(
            "filter_out_existing_chunks", True
        )

        logger = input.message.get("logger", logging.getLogger())

        logger.info(
            f"KGExtractionPipe: Processing document {document_id} for KG extraction",
        )

        # Then create the extractions from the results
        extractions = [
            DocumentChunk(
                id=extraction["id"],
                document_id=extraction["document_id"],
                owner_id=extraction["owner_id"],
                collection_ids=extraction["collection_ids"],
                data=extraction["text"],
                metadata=extraction["metadata"],
            )
            for extraction in (
                await self.database_provider.list_document_chunks(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
                    document_id=document_id,
                    offset=0,
                    limit=100,
                )
            )["results"]
        ]

        logger.info(
            f"Found {len(extractions)} extractions for document {document_id}"
        )

        if filter_out_existing_chunks:
            existing_chunk_ids = await self.database_provider.graph_handler.get_existing_document_entity_chunk_ids(
                document_id=document_id
            )
            extractions = [
                extraction
                for extraction in extractions
                if extraction.id not in existing_chunk_ids
            ]
            logger.info(
                f"Filtered out {len(existing_chunk_ids)} existing extractions, remaining {len(extractions)} extractions for document {document_id}"
            )

            if len(extractions) == 0:
                logger.info(f"No extractions left for document {document_id}")
                return

        logger.info(
            f"KGExtractionPipe: Obtained {len(extractions)} extractions to process, time from start: {time.time() - start_time:.2f} seconds",
        )

        # sort the extractions accroding to chunk_order field in metadata in ascending order
        extractions = sorted(
            extractions,
            key=lambda x: x.metadata.get("chunk_order", float("inf")),
        )

        # group these extractions into groups of chunk_merge_count
        extractions_groups = [
            extractions[i : i + chunk_merge_count]
            for i in range(0, len(extractions), chunk_merge_count)
        ]

        logger.info(
            f"KGExtractionPipe: Extracting KG Relationships for document and created {len(extractions_groups)} tasks, time from start: {time.time() - start_time:.2f} seconds",
        )

        tasks = [
            asyncio.create_task(
                self.extract_kg(
                    extractions=extractions_group,
                    generation_config=generation_config,
                    max_knowledge_relationships=max_knowledge_relationships,
                    entity_types=entity_types,
                    relation_types=relation_types,
                    task_id=task_id,
                    total_tasks=len(extractions_groups),
                )
            )
            for task_id, extractions_group in enumerate(extractions_groups)
        ]

        completed_tasks = 0
        total_tasks = len(tasks)

        logger.info(
            f"KGExtractionPipe: Waiting for {total_tasks} KG extraction tasks to complete",
        )

        for completed_task in asyncio.as_completed(tasks):
            try:
                yield await completed_task
                completed_tasks += 1
                if completed_tasks % 100 == 0:
                    logger.info(
                        f"KGExtractionPipe: Completed {completed_tasks}/{total_tasks} KG extraction tasks",
                    )
            except Exception as e:
                logger.error(f"Error in Extracting KG Relationships: {e}")
                yield R2RDocumentProcessingError(
                    document_id=document_id,
                    error_message=str(e),
                )

        logger.info(
            f"KGExtractionPipe: Completed {completed_tasks}/{total_tasks} KG extraction tasks, time from start: {time.time() - start_time:.2f} seconds",
        )
