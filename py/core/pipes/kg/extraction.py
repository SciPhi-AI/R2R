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
    RunLoggingSingleton,
    Triple,
)
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


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

    def map_to_str(self, fragment: DocumentFragment) -> str:
        # convert fragment to dict object
        fragment = json.loads(json.dumps(fragment))
        return fragment

    async def extract_kg(
        self,
        fragment: DocumentFragment,
        generation_config: GenerationConfig,
        retries: int = 3,
        delay: int = 2,
    ) -> KGExtraction:
        """
        Extracts NER triples from a fragment with retries.
        """

        task_inputs = {"input": fragment.data}
        task_inputs["max_knowledge_triples"] = (
            self.kg_provider.config.kg_creation_settings.max_knowledge_triples
        )

        messages = self.prompt_provider._get_message_payload(
            task_prompt_name=self.kg_provider.config.kg_extraction_prompt,
            task_inputs=task_inputs,
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
                            document_ids=[str(fragment.document_id)],
                            text_unit_ids=[str(fragment.id)],
                            attributes={"fragment_text": fragment.data},
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
                                document_ids=[str(fragment.document_id)],
                                text_unit_ids=[str(fragment.id)],
                                attributes={"fragment_text": fragment.data},
                            )
                        )

                    return entities_dict, relations_arr

                entities, triples = parse_fn(kg_extraction)
                return KGExtraction(
                    fragment_id=fragment.id,
                    document_id=fragment.document_id,
                    entities=entities,
                    triples=triples,
                )

            except (
                ClientError,
                json.JSONDecodeError,
                KeyError,
                IndexError,
            ) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Failed after retries with for fragment {fragment.id} of document {fragment.document_id}: {e}"
                    )
                    raise e

        # add metadata to entities and triples

        return KGExtraction(
            fragment_id=fragment.id,
            document_id=fragment.document_id,
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

        extractions = [
            DocumentFragment(
                id=extraction["fragment_id"],
                extraction_id=extraction["extraction_id"],
                document_id=extraction["document_id"],
                user_id=extraction["user_id"],
                group_ids=extraction["group_ids"],
                data=extraction["text"],
                metadata=extraction["metadata"],
            )
            for extraction in self.database_provider.vector.get_document_chunks(
                document_id=document_id
            )
        ]

        tasks = [
            asyncio.create_task(self.extract_kg(extraction, generation_config))
            for extraction in extractions
        ]

        for completed_task in asyncio.as_completed(tasks):
            try:
                yield await completed_task
            except Exception as e:
                logger.error(f"Error in Extracting KG Triples: {e}")
                raise R2RDocumentProcessingError(
                    document_id=document_id,
                    error=str(e),
                ) from e
