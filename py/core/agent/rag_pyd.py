import logging
from typing import Callable, Optional

from pydantic_ai import Agent as PydanticAgent

from core.base import (
    Message,
)
from core.base.abstractions import (
    GenerationConfig,
    SearchSettings,
)
from core.base.agent.tools.registry import ToolRegistry
from core.base.providers import DatabaseProvider
from core.providers import (
    AnthropicCompletionProvider,
    LiteLLMCompletionProvider,
    OpenAICompletionProvider,
    R2RCompletionProvider,
)

from ..base.agent.agent import RAGAgentConfig  # type: ignore
from .rag import R2RRAGAgent  # type: ignore

logger = logging.getLogger(__name__)

INSTRUCTIONS = """
You are a helpful agent that can search for information, the date is {date}.

If you have access to tools that help you set some filters, like smart_filter_tool, to narrow down and speed up the search, use them BEFORE the search
When asked a question, YOU SHOULD ALWAYS USE YOUR SEARCH TOOL TO ATTEMPT TO SEARCH FOR RELEVANT INFORMATION THAT ANSWERS THE USER QUESTION.

The response should contain line-item attributions to relevant search results, and be as informative if possible.

If no relevant results are found, then state that no results were found. If no obvious question is present, then do not carry out a search, and instead ask for clarification.

REMINDER - Use line item references to like [c910e2e], [b12cd2f], to refer to the specific search result IDs returned in the provided context.
"""


def pydantic_to_r2r_message(pydantic_response) -> list[Message]:
    messages = []
    logger.debug(f"Pydantic response: {pydantic_response}")
    try:
        all_messages = pydantic_response.all_messages
        logger.debug(f"All messages: {all_messages}")
    except Exception as e:
        logger.error(f"Error getting all messages: {e}")
        all_messages = []
    if hasattr(pydantic_response, "output"):
        messages.append(
            Message(
                role="assistant",
                content=pydantic_response.output,
            )
        )
    return messages


class RAGPydAgent(R2RRAGAgent):
    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: RAGAgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        tool_registry: Optional[ToolRegistry] = None,
        max_tool_context_length: int = 20_000,
        **kwargs,
    ):
        super().__init__(
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            tool_registry=tool_registry,
            max_tool_context_length=max_tool_context_length,
            **kwargs,
        )
        # Init pydantic agent
        self._pydantic_tools = [
            tool._pydantic_ai_tool
            for tool in getattr(self, "_tools", [])
            if hasattr(tool, "_pydantic_ai_tool")
        ]
        self._pydantic_agent = PydanticAgent(
            model=self.get_pyd_ai_model_name(rag_generation_config.model),
            tools=self._pydantic_tools,
            name="R2R Pydantic Agent",
            instructions=INSTRUCTIONS,
        )

    def get_pyd_ai_model_name(self, model_name: str | None):
        logger.debug(f"Fetching model name from: {model_name}")
        if not model_name:
            raise ValueError("Model name is required")
        if "gpt" in model_name:
            # Initialize the model with our reverse proxy
            # remove openai/ prefix if there is one
            model_id = model_name.replace("openai/", "")
            return model_id
        else:
            raise ValueError(f"Model {model_name} is not supported")

    async def arun(self, messages: list[Message], **kwargs):
        # logger.debug(f"Running pydantic agent with messages: {messages}")
        message = messages[0].content
        # logger.debug(f"Message: {message}")
        py_response = await self._pydantic_agent.run(message)
        r2r_response = pydantic_to_r2r_message(py_response)
        return r2r_response
