"""
A simple example to demonstrate the usage of `AgentRAGPipeline`.
"""

import json
import logging
import re
from typing import Optional

from r2r.core import GenerationConfig
from r2r.core.abstractions.output import RAGPipelineOutput

from ..web.rag import WebRAGPipeline

logger = logging.getLogger(__name__)


# TODO: This can be moved somewhere.
agent_rag_prompt = """
You are a helpful assistant with access to web search whose job it is to answer users questions.
The following is a conversation with a user - after each new user message your task is to generate
a search query or ask a follow up question.

For example, here is a sketch of a conversation:
'''
User: Hi I want to get dinner
Assistant: Where are you located?
User: New York City
Assistant: <search>Places to eat in New York City</search>
'''

Here is another example:
'''
User: I want to get dinner in NYC
Assistant: <search>Places to eat in New York City</search>
'''

Be sure to ask specific questsions such that a single search is likely to return actionable results to the user.
Begin.

{query}
"""


class AgentRAGPipeline(WebRAGPipeline):
    def __init__(self, *args, **kwargs):
        logger.info(f"Initalizing `AgentRAGPipeline`.")
        super().__init__(*args, **kwargs)

    def transform_query(self, query: str) -> str:
        return agent_rag_prompt.format(query=query)

    # Returns a web search query to execute or None if it needed additional context.
    def generate_search_query(self, response: str):
        match = re.match(r"<search>(.*)</search>", response)
        return match.group(1) if match else None

    def run(
        self,
        query,
        filters={},
        limit=10,
        search_only=False,
        generation_config: Optional[GenerationConfig] = None,
        *args,
        **kwargs,
    ) -> str:
        self.initialize_pipeline(query, False)

        # Extracts the full conversation history from the query.
        # Query is the json encoded message history given as a list of objects as following:
        # [
        #   {
        #     "role": "user",
        #     "content": "my previous message",
        #   }, ...
        # ]
        conversation = json.loads(query)
        conversation[0]["content"] = self.transform_query(
            conversation[0]["content"]
        )
        prompt, conversation = conversation[-1]["content"], conversation[:-1]

        completion = self.generate_completion(
            prompt, generation_config, conversation=conversation
        )
        search_query = self.generate_search_query(
            completion.choices[0].message.content
        )

        if not search_query:
            return RAGPipelineOutput(search_results=[], completion=completion)

        search_results = self.search(search_query, filters={}, limit=5)
        return RAGPipelineOutput(search_results, None, None)
