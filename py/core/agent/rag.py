# type: ignore
import logging
from typing import Callable, Optional

from core.base import (
    format_search_results_for_llm,
)
from core.base.abstractions import (
    AggregateSearchResult,
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
from core.utils import (
    SearchResultsCollector,
    num_tokens,
)

from ..base.agent.agent import RAGAgentConfig

# Import the base classes from the refactored base file
from .base import (
    R2RAgent,
    R2RStreamingAgent,
    R2RXMLStreamingAgent,
    R2RXMLToolsAgent,
)

logger = logging.getLogger(__name__)


class RAGAgentMixin:
    """
    A Mixin for adding search_file_knowledge, web_search, and content tools
    to your R2R Agents. This allows your agent to:
      - call knowledge_search_method (semantic/hybrid search)
      - call content_method (fetch entire doc/chunk structures)
      - call an external web search API
    """

    def __init__(
        self,
        *args,
        search_settings: SearchSettings,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length=10_000,
        max_context_window_tokens=512_000,
        tool_registry: Optional[ToolRegistry] = None,
        **kwargs,
    ):
        # Save references to the retrieval logic
        self.search_settings = search_settings
        self.knowledge_search_method = knowledge_search_method
        self.content_method = content_method
        self.file_search_method = file_search_method
        self.max_tool_context_length = max_tool_context_length
        self.max_context_window_tokens = max_context_window_tokens
        self.search_results_collector = SearchResultsCollector()
        self.tool_registry = tool_registry or ToolRegistry()

        super().__init__(*args, **kwargs)

    def _register_tools(self):
        """
        Register all requested tools from self.config.rag_tools using the ToolRegistry.
        """
        if not self.config.rag_tools:
            logger.warning(
                "No RAG tools requested. Skipping tool registration."
            )
            return

        # Make sure tool_registry exists
        if not hasattr(self, "tool_registry") or self.tool_registry is None:
            self.tool_registry = ToolRegistry()

        format_function = self.format_search_results_for_llm

        for tool_name in set(self.config.rag_tools):
            # Try to get the tools from the registry
            if tool_instance := self.tool_registry.create_tool_instance(
                tool_name, format_function, context=self
            ):
                logger.debug(
                    f"Successfully registered tool from registry: {tool_name}"
                )
                self._tools.append(tool_instance)
            else:
                logger.warning(f"Unknown tool requested: {tool_name}")

        logger.debug(f"Registered {len(self._tools)} RAG tools.")

    def format_search_results_for_llm(
        self, results: AggregateSearchResult
    ) -> str:
        context = format_search_results_for_llm(
            results, self.search_results_collector
        )
        context_tokens = num_tokens(context) + 1
        frac_to_return = self.max_tool_context_length / (context_tokens)

        if frac_to_return > 1:
            return context
        else:
            return context[: int(frac_to_return * len(context))]


class R2RRAGAgent(RAGAgentMixin, R2RAgent):
    """
    Non-streaming RAG Agent that supports search_file_knowledge, content, web_search.
    """

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
    ):
        # Initialize base R2RAgent
        R2RAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
        )
        self.tool_registry = tool_registry or ToolRegistry()
        # Initialize the RAGAgentMixin
        RAGAgentMixin.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            max_tool_context_length=max_tool_context_length,
            knowledge_search_method=knowledge_search_method,
            file_search_method=file_search_method,
            content_method=content_method,
            tool_registry=tool_registry,
        )

        self._register_tools()


class R2RXMLToolsRAGAgent(RAGAgentMixin, R2RXMLToolsAgent):
    """
    Non-streaming RAG Agent that supports search_file_knowledge, content, web_search.
    """

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
    ):
        # Initialize base R2RAgent
        R2RXMLToolsAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
        )
        self.tool_registry = tool_registry or ToolRegistry()
        # Initialize the RAGAgentMixin
        RAGAgentMixin.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            max_tool_context_length=max_tool_context_length,
            knowledge_search_method=knowledge_search_method,
            file_search_method=file_search_method,
            content_method=content_method,
            tool_registry=tool_registry,
        )

        self._register_tools()


class R2RStreamingRAGAgent(RAGAgentMixin, R2RStreamingAgent):
    """
    Streaming-capable RAG Agent that supports search_file_knowledge, content, web_search,
    and emits citations as [abc1234] short IDs if the LLM includes them in brackets.
    """

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
        max_tool_context_length: int = 10_000,
    ):
        # Force streaming on
        config.stream = True

        # Initialize base R2RStreamingAgent
        R2RStreamingAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
        )
        self.tool_registry = tool_registry or ToolRegistry()
        # Initialize the RAGAgentMixin
        RAGAgentMixin.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            max_tool_context_length=max_tool_context_length,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            tool_registry=tool_registry,
        )

        self._register_tools()


class R2RXMLToolsStreamingRAGAgent(RAGAgentMixin, R2RXMLStreamingAgent):
    """
    A streaming agent that:
     - treats <think> or <Thought> blocks as chain-of-thought
       and emits them incrementally as SSE "thinking" events.
     - accumulates user-visible text outside those tags as SSE "message" events.
     - filters out all XML tags related to tool calls and actions.
     - upon finishing each iteration, it parses <Action><ToolCalls><ToolCall> blocks,
       calls the appropriate tool, and emits SSE "tool_call" / "tool_result".
     - properly emits citations when they appear in the text
    """

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
        max_tool_context_length: int = 10_000,
    ):
        # Force streaming on
        config.stream = True

        # Initialize base R2RXMLStreamingAgent
        R2RXMLStreamingAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
        )
        self.tool_registry = tool_registry or ToolRegistry()
        # Initialize the RAGAgentMixin
        RAGAgentMixin.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            max_tool_context_length=max_tool_context_length,
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
            tool_registry=tool_registry,
        )

        self._register_tools()
