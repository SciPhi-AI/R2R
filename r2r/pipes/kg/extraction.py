import asyncio
import json
import logging
import re
import uuid
from typing import Any, AsyncGenerator, Optional, Union

from r2r.base import (
    AsyncState,
    ChunkingProvider,
    CompletionProvider,
    DocumentExtraction,
    DocumentFragment,
    Entity,
    KGExtraction,
    KGProvider,
    PipeType,
    PromptProvider,
    R2RDocumentProcessingError,
    RunLoggingSingleton,
    Triple,
    extract_entities,
    extract_triples,
)
from r2r.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class ClientError(Exception):
    """Base class for client connection errors."""

    pass


class KGExtractionPipe(AsyncPipe):
    """
    Extracts knowledge graph information from document extractions.
    """

    class Input(AsyncPipe.Input):
        message: AsyncGenerator[
            Union[DocumentExtraction, R2RDocumentProcessingError], None
        ]

    def __init__(
        self,
        kg_provider: KGProvider,
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
        retries: int = 3,
        delay: int = 2,
    ) -> KGExtraction:
        """
        Extracts NER triples from a fragment with retries.
        """

        task_inputs = {"input": fragment.data}
        if self.graph_rag:
            task_inputs["max_knowledge_triplets"] = 100

        messages = self.prompt_provider._get_message_payload(
            task_prompt_name=self.kg_provider.config.kg_extraction_prompt,
            task_inputs=task_inputs,
        )

        for attempt in range(retries):

            try:
                response = await self.llm_provider.aget_completion(
                    messages, self.kg_provider.config.kg_extraction_config
                )

                kg_extraction = response.choices[0].message.content

                if self.graph_rag:

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
                            logger.info(f"Entity: {entity}")
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
                            logger.info(f"Relationship: {relationship}")
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
                                    attributes={
                                        "fragment_text": fragment.data
                                    },
                                )
                            )

                        return entities_dict, relations_arr

                    entities, triples = parse_fn(kg_extraction)
                    return KGExtraction(
                        entities=list(entities.values()), triples=triples
                    )

                else:
                    # Parsing JSON from the response
                    kg_json = (
                        json.loads(
                            kg_extraction.split("```json")[1].split("```")[0]
                        )
                        if "```json" in kg_extraction
                        else json.loads(kg_extraction)
                    )
                    llm_payload = kg_json.get("entities_and_triples", {})

                    # Extract triples with detailed logging
                    entities = extract_entities(llm_payload)
                    triples = extract_triples(llm_payload, entities)

                    # Create KG extraction object
                    return KGExtraction(
                        entities=entities.values(), triples=triples
                    )

            except (
                ClientError,
                json.JSONDecodeError,
                KeyError,
                IndexError,
            ) as e:
                logger.error(f"Error in extract_kg: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed after retries with {e}")

        # add metadata to entities and triples

        return KGExtraction(entities={}, triples=[])

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: Any,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[KGExtraction, R2RDocumentProcessingError], None]:

        async def process_extraction(extraction):
            return await self.extract_kg(extraction)

        extractions = []
        async for extraction in input.message:
            extractions.append(extraction)

        kg_extractions = await asyncio.gather(
            *[process_extraction(extraction) for extraction in extractions]
        )

        for kg_extraction in kg_extractions:
            yield kg_extraction
