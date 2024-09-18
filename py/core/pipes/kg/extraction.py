import asyncio
import json
import logging
import re
import uuid
from typing import Any, AsyncGenerator, Optional, Union

from core.base import (
    AsyncState,
    ChunkingProvider,
    CompletionProvider,
    DatabaseProvider,
    DocumentFragment,
    Entity,
    GenerationConfig,
    KGExtraction,
    KGProvider,
    PipeType,
    PromptProvider,
    R2RDocumentProcessingError,
    R2RException,
    RunLoggingSingleton,
    Triple,
)
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


MIN_VALID_KG_EXTRACTION_RESPONSE_LENGTH = 128


class ClientError(Exception):
    """Base class for client connection errors."""

    pass


class KGTriplesExtractionPipe(AsyncPipe):
    """
    Extracts knowledge graph information from document extractions.
    """

    class Input(AsyncPipe.Input):
        message: dict

    def __init__(
        self,
        kg_provider: KGProvider,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        chunking_provider: ChunkingProvider,
        kg_batch_size: int = 1,
        graph_rag: bool = True,
        id_prefix: str = "demo",
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config
            or AsyncPipe.PipeConfig(name="default_kg_extraction_pipe"),
        )
        self.kg_provider = kg_provider
        self.prompt_provider = prompt_provider
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.chunking_provider = chunking_provider
        self.kg_batch_size = kg_batch_size
        self.id_prefix = id_prefix
        self.pipe_run_info = None
        self.graph_rag = graph_rag

    def map_to_str(self, fragments: list[DocumentFragment]) -> str:
        # convert fragment to dict object
        fragment = json.loads(json.dumps(fragment))
        return fragment

    async def extract_kg(
        self,
        fragments: list[DocumentFragment],
        generation_config: GenerationConfig,
        max_knowledge_triples: int,
        entity_types: list[str],
        relation_types: list[str],
        retries: int = 3,
        delay: int = 2,
    ) -> KGExtraction:
        """
        Extracts NER triples from a fragment with retries.
        """
        # combine all fragments into a single string
        combined_fragment = " ".join([fragment.data for fragment in fragments])

        messages = self.prompt_provider._get_message_payload(
            task_prompt_name=self.kg_provider.config.kg_extraction_prompt,
            task_inputs={
                "input": combined_fragment,
                "max_knowledge_triples": max_knowledge_triples,
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
                            "No entities found in the response string, the selected LLM likely failed to format it's response correctly.",
                            400,
                        )
                    relationships = re.findall(
                        relationship_pattern, response_str
                    )

                    entities_dict = {}
                    for entity in entities:
                        entity_value = entity[0]
                        entity_category = entity[1]
                        entity_description = entity[2]
                        entities_dict[entity_value] = Entity(
                            category=entity_category,
                            description=entity_description,
                            name=entity_value,
                            document_ids=[str(fragments[0].document_id)],
                            text_unit_ids=[
                                str(fragment.id) for fragment in fragments
                            ],
                            attributes={"fragment_text": combined_fragment},
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
                            Triple(
                                id=str(uuid.uuid4()),
                                subject=subject,
                                predicate=predicate,
                                object=object,
                                description=description,
                                weight=weight,
                                document_ids=[str(fragments[0].document_id)],
                                text_unit_ids=[
                                    str(fragment.id) for fragment in fragments
                                ],
                                attributes={
                                    "fragment_text": combined_fragment
                                },
                            )
                        )

                    return entities_dict, relations_arr

                entities, triples = parse_fn(kg_extraction)
                return KGExtraction(
                    fragment_ids=[fragment.id for fragment in fragments],
                    document_id=fragments[0].document_id,
                    entities=entities,
                    triples=triples,
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
                        f"Failed after retries with for fragment {fragments[0].id} of document {fragments[0].document_id}: {e}"
                    )
                    raise e

        # add metadata to entities and triples

        return KGExtraction(
            fragment_ids=[fragment.id for fragment in fragments],
            document_id=fragments[0].document_id,
            entities={},
            triples=[],
        )

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: Any,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[KGExtraction, R2RDocumentProcessingError], None]:

        logger.info("Running KG Extraction Pipe")

        document_id = input.message["document_id"]
        generation_config = input.message["generation_config"]
        fragment_merge_count = input.message["fragment_merge_count"]
        max_knowledge_triples = input.message["max_knowledge_triples"]
        entity_types = input.message["entity_types"]
        relation_types = input.message["relation_types"]

        fragments = [
            DocumentFragment(
                id=extraction["fragment_id"],
                extraction_id=extraction["extraction_id"],
                document_id=extraction["document_id"],
                user_id=extraction["user_id"],
                collection_ids=extraction["collection_ids"],
                data=extraction["text"],
                metadata=extraction["metadata"],
            )
            for extraction in self.database_provider.vector.get_document_chunks(
                document_id=document_id
            )
        ]

        # sort the fragments accroding to chunk_order field in metadata in ascending order
        fragments = sorted(fragments, key=lambda x: x.metadata["chunk_order"])

        # group these extractions into groups of fragment_merge_count
        fragments_groups = [
            fragments[i : i + fragment_merge_count]
            for i in range(0, len(fragments), fragment_merge_count)
        ]

        logger.info(
            f"Extracting KG Triples from {len(fragments_groups)} fragment groups from originally {len(fragments)} fragments for document {document_id}"
        )

        tasks = [
            asyncio.create_task(
                self.extract_kg(
                    fragments=fragments_group,
                    generation_config=generation_config,
                    max_knowledge_triples=max_knowledge_triples,
                    entity_types=entity_types,
                    relation_types=relation_types,
                )
            )
            for fragments_group in fragments_groups
        ]

        for completed_task in asyncio.as_completed(tasks):
            try:
                yield await completed_task
            except Exception as e:
                logger.error(f"Error in Extracting KG Triples: {e}")
                yield R2RDocumentProcessingError(
                    document_id=document_id,
                    error_message=str(e),
                )
