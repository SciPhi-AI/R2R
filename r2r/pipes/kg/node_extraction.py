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
    CompletionProvider,
    PromptProvider,
    R2RDocumentProcessingError,
    KVLoggingSingleton,
    PipeType,
)

from r2r.base.abstractions.graph import Triple, Entity

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
        llm_provider: CompletionProvider,
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
        
        nodes = self.kg_provider.get_entity_map()

        for node_value, node_info in nodes.items(): 
            for entity in node_info['entities']:
                yield entity, node_info['triples'] # the entity and its associated triples

class KGNodeDescriptionPipe(AsyncPipe):
    """
        The pipe takes input a list of nodes and extracts description from them.
    """

    class Input(AsyncPipe.Input):
        message: AsyncGenerator[tuple[Entity, list[Triple]], None]

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: CompletionProvider,
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


        # summarization_content  = """

        #     You are given the following entity and its associated triples:
        #     Entity: {entity_info}
        #     Triples: {triples_txt}
        #     Your tasks:

        #     Entity Description:
        #     Provide a concise description of the entity based on the given information and triples.

        #     Entity Analysis:
        #     a) Determine if this entity represents a single concept or a combination of multiple entities.
        #     b) If it's a combination, list the separate entities that make up this composite entity.
        #     c) Map each separate entity to the relationship(s) it came from in the original triples.
        #     d) Suggest more appropriate names for each separate entity if applicable.

        #     Formatted Output:
        #     For each entity (original or separate), provide the following formatted output:
        #     ("entity"$$$$<entity_name>$$$$<entity_type>$$$$<entity_description>$$$$<associated_triples>)

        #     Where:
        #     <entity_name>: The name of the entity (original or improved)
        #     <entity_type>: The type or category of the entity
        #     <entity_description>: A concise description of the entity
        #     <associated_triples>: List of triples associated with this specific entity


        #     Explanation:
        #     Briefly explain your reasoning for separating entities (if applicable) and any name changes you suggested.

        #     Please ensure your response is clear, concise, and follows the requested format.            
        # """

        summarization_content = """

            Give a concise summary of the entity and its associated triples.

            Entity: {entity_info}
            Triples: {triples_txt}

        """

        async for entity, triples in input.message:            

            entity_info = f'{entity.value}, {entity.description}'
            triples_txt = '\n'.join([f"{i+1}: {triple.subject}, {triple.object}, {triple.predicate} - Summary: {triple.description}" for i, triple in enumerate(triples)])

            messages = [{'role':'user', 'content': summarization_content.format(entity_info=entity_info, triples_txt=triples_txt)}]
  
            out_entity = self.kg_provider.retrieve_cache('entities_with_description', f'{entity.id}_{entity.value}')
            if out_entity:
                logger.info(f"Hit cache for entity {entity.value}")
            else:
                completion = await self.llm_provider.aget_completion(messages, GenerationConfig(model='gpt-4o-mini'))

                # parse the output 
                # import re 
                # pattern = r'\("entity"$$$$([^$]+)$$$$([^$]+)$$$$([^$]+)$$$$([^$]+)\)'
                # matches = re.findall(pattern, completion.choices[0].message.content)

                # if len(matches) > 1:
    
                entity.description = completion.choices[0].message.content

                # entity.description_embedding = self.embedding_provider.get_embedding(entity.description)

                self.kg_provider.upsert_nodes([entity], with_description=True)
                out_entity = entity
                
            yield entity