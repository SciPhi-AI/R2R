# pipe to extract nodes/triples etc

import asyncio
import logging
import uuid
from typing import AsyncGenerator, Optional, Union, Any
from r2r.base.providers.llm import GenerationConfig

from r2r.base import (
    AsyncState,
    EmbeddingProvider,
    KGExtraction,
    KGProvider,
    LLMProvider,
    PromptProvider,
    R2RDocumentProcessingError,
    KVLoggingSingleton,
    PipeType,
)

from r2r.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)

class KGNodeExtractionPipe(AsyncPipe):
    """
        The pipe takes input a list of documents (optional) and extracts nodes and triples from them.
    """

    class Input(AsyncPipe.Input):
        message: Any

    def __init__(self, 
        kg_provider: KGProvider,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args, **kwargs
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config or AsyncPipe.PipeConfig(name="kg_node_extraction_pipe"),
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider

    async def _run_logic(self, input: Input, state: AsyncState, run_id: uuid.UUID, *args, **kwargs) -> AsyncGenerator[Any, None]:
        nodes = self.kg_provider.get()

        for node in nodes: 
            yield node

class KGNodeDescriptionPipe(AsyncPipe):
    """
        The pipe takes input a list of nodes and extracts description from them.
    """

    class Input(AsyncPipe.Input):
        message: AsyncGenerator[Any, None]

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: LLMProvider,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args, **kwargs
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config or AsyncPipe.PipeConfig(name="kg_node_description_pipe"),
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        

    async def _run_logic(self, input: Input, state: AsyncState, run_id: uuid.UUID, *args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        """
            Extracts description from the input.
        """

        async for node in input.message:            
            messages = [{'role':'user', 'content': 'Summarize the following text: ' + str(node)}]
            completion = await self.llm_provider.aget_completion(messages, GenerationConfig(model='gpt-4o-mini'))
            yield node, completion