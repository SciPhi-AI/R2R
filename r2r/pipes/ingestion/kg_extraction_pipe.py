import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Optional, Union

from r2r.base import (
    AsyncState,
    ChunkingProvider,
    CompletionProvider,
    Extraction,
    Fragment,
    KGExtraction,
    KGProvider,
    KVLoggingSingleton,
    PipeType,
    PromptProvider,
    R2RDocumentProcessingError,
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
            Union[Extraction, R2RDocumentProcessingError], None
        ]

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        chunking_provider: ChunkingProvider,
        kg_batch_size: int = 1,
        pipe_logger: Optional[KVLoggingSingleton] = None,
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

    async def extract_kg(
        self,
        fragment: Any,
        retries: int = 3,
        delay: int = 2,
    ) -> KGExtraction:
        """
        Extracts NER triples from a fragment with retries.
        """
        messages = self.prompt_provider._get_message_payload(
            task_prompt_name=self.kg_provider.config.kg_extraction_prompt,
            task_inputs={"input": fragment},
        )
        for attempt in range(retries):
            try:
                response = await self.llm_provider.aget_completion(
                    messages, self.kg_provider.config.kg_extraction_config
                )

                kg_extraction = response.choices[0].message.content

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
                return KGExtraction(entities=entities, triples=triples)
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

        return KGExtraction(entities={}, triples=[])

    async def _process_batch(
        self, fragment_batch: list[Any]
    ) -> list[KGExtraction]:
        """
        Processes a batch of fragments and extracts KG information.
        """
        tasks = [
            asyncio.create_task(self.extract_kg(fragment))
            for fragment in fragment_batch
        ]
        return await asyncio.gather(*tasks)

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: Any,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[KGExtraction, R2RDocumentProcessingError], None]:
        fragment_batch = []

        async for item in input.message:
            if isinstance(item, R2RDocumentProcessingError):
                yield item
                continue

            try:
                async for chunk in self.chunking_provider.chunk(item.data):
                    fragment_batch.append(chunk)
                    if len(fragment_batch) >= self.kg_batch_size:
                        for kg_extraction in await self._process_batch(
                            fragment_batch
                        ):
                            yield kg_extraction
                        fragment_batch.clear()
            except Exception as e:
                logger.error(f"Error processing document: {e}")
                yield R2RDocumentProcessingError(
                    error_message=str(e),
                    document_id=item.document_id,
                )

        if fragment_batch:
            try:
                for kg_extraction in await self._process_batch(fragment_batch):
                    yield kg_extraction
            except Exception as e:
                logger.error(f"Error processing final batch: {e}")
                yield R2RDocumentProcessingError(
                    error_message=str(e),
                    document_id=(
                        fragment_batch[0].document_id
                        if fragment_batch
                        else None
                    ),
                )
