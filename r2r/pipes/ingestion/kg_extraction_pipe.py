import asyncio
import copy
import json
import logging
import uuid
from typing import Any, AsyncGenerator, Optional

from aiohttp import ClientError

from r2r.base import (
    AsyncState,
    Extraction,
    Fragment,
    FragmentType,
    KGExtraction,
    KGProvider,
    KVLoggingSingleton,
    LLMProvider,
    PipeType,
    PromptProvider,
    TextSplitter,
    extract_entities,
    extract_triples,
    generate_id_from_label,
)
from r2r.base.abstractions.llm import GenerationConfig
from r2r.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class KGExtractionPipe(AsyncPipe):
    """
    Embeds and stores documents using a specified embedding model and database.
    """

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        text_splitter: TextSplitter,
        kg_batch_size: int = 1,
        id_prefix: str = "demo",
        pipe_logger: Optional[KVLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the embedding pipe with necessary components and configurations.
        """
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config
            or AsyncPipe.PipeConfig(name="default_embedding_pipe"),
        )
        self.kg_provider = kg_provider
        self.prompt_provider = prompt_provider
        self.llm_provider = llm_provider
        self.text_splitter = text_splitter
        self.kg_batch_size = kg_batch_size
        self.id_prefix = id_prefix
        self.pipe_run_info = None

    async def fragment(
        self, extraction: Extraction, run_id: uuid.UUID
    ) -> AsyncGenerator[Fragment, None]:
        """
        Splits text into manageable chunks for embedding.
        """
        if not isinstance(extraction, Extraction):
            raise ValueError(
                f"Expected an Extraction, but received {type(extraction)}."
            )
        if not isinstance(extraction.data, str):
            raise ValueError(
                f"Expected a string, but received {type(extraction.data)}."
            )
        text_chunks = [
            ele.page_content
            for ele in self.text_splitter.create_documents([extraction.data])
        ]
        for iteration, chunk in enumerate(text_chunks):
            fragment = Fragment(
                id=generate_id_from_label(f"{extraction.id}-{iteration}"),
                type=FragmentType.TEXT,
                data=chunk,
                metadata=copy.deepcopy(extraction.metadata),
                extraction_id=extraction.id,
                document_id=extraction.document_id,
            )
            yield fragment

    async def transform_fragments(
        self, fragments: list[Fragment], metadatas: list[dict]
    ) -> AsyncGenerator[Fragment, None]:
        """
        Transforms text chunks based on their metadata, e.g., adding prefixes.
        """
        async for fragment, metadata in zip(fragments, metadatas):
            if "chunk_prefix" in metadata:
                prefix = metadata.pop("chunk_prefix")
                fragment.data = f"{prefix}\n{fragment.data}"
            yield fragment

    async def extract_kg(
        self,
        fragment: Fragment,
        kg_generation_config: GenerationConfig,
        retries: int = 3,
        delay: int = 2,
    ) -> KGExtraction:
        """
        Extracts NER triples from a list of fragments with retries.
        """
        task_prompt = self.prompt_provider.get_prompt(
            self.kg_provider.config.kg_extraction_prompt,
            inputs={"input": fragment.data},
        )
        messages = self.prompt_provider._get_message_payload(
            self.prompt_provider.get_prompt("default_system"), task_prompt
        )
        for attempt in range(retries):
            try:
                response = await self.llm_provider.aget_completion(
                    messages, kg_generation_config
                )

                kg_extraction = response.choices[0].message.content

                # Parsing JSON from the response
                kg_json = json.loads(
                    kg_extraction.split("```json")[1].split("```")[0]
                )

                llm_payload = kg_json.get("entities_and_triplets", {})

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
                    # raise e  # Ensure the exception is raised after the final attempt

        return KGExtraction(entities=[], triples=[])

    async def _process_batch(
        self,
        fragment_batch: list[Fragment],
        kg_generation_config: GenerationConfig,
    ) -> list[KGExtraction]:
        """
        Embeds a batch of fragments and yields vector entries.
        """
        tasks = [
            asyncio.create_task(
                self.extract_kg(fragment, kg_generation_config)
            )
            for fragment in fragment_batch
        ]
        return await asyncio.gather(*tasks)

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        kg_generation_config: GenerationConfig = GenerationConfig(
            model="gpt-4o", temperature=0.0
        ),
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[KGExtraction, None]:
        """
        Executes the embedding pipe: chunking, transforming, embedding, and storing documents.
        """
        batch_tasks = []
        fragment_batch = []

        fragment_info = {}
        async for extraction in input.message:
            async for fragment in self.fragment(extraction, run_id):
                if extraction.document_id in fragment_info:
                    fragment_info[extraction.document_id] += 1
                else:
                    fragment_info[extraction.document_id] = 1
                extraction.metadata["chunk_order"] = fragment_info[
                    extraction.document_id
                ]
                fragment_batch.append(fragment)
                if len(fragment_batch) >= self.kg_batch_size:
                    # Here, ensure `_process_batch` is scheduled as a coroutine, not called directly
                    batch_tasks.append(
                        self._process_batch(
                            fragment_batch.copy(), kg_generation_config
                        )
                    )  # pass a copy if necessary
                    fragment_batch.clear()  # Clear the batch for new fragments

        logger.debug(
            f"Fragmented the input document ids into counts as shown: {fragment_info}"
        )

        if fragment_batch:  # Process any remaining fragments
            batch_tasks.append(self._process_batch(fragment_batch.copy()))

        # Process tasks as they complete
        for task in asyncio.as_completed(batch_tasks):
            batch_result = await task  # Wait for the next task to complete
            for kg_extraction in batch_result:
                yield kg_extraction
