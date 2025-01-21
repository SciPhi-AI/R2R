from datetime import datetime
from typing import Optional

from core.agent import R2RAgent, R2RStreamingAgent
from core.base import (
    format_search_results_for_llm,
    format_search_results_for_stream,
)
from core.base.abstractions import (
    AggregateSearchResult,
    GenerationConfig,
    Message,
    SearchSettings,
    WebSearchResponse,
)
from core.base.agent import AgentConfig, Tool
from core.base.providers import DatabaseProvider
from core.providers import LiteLLMCompletionProvider, OpenAICompletionProvider


class RAGAgentMixin:
    def __init__(self, *args, local_search_method=None, **kwargs):
        # Add local_search_method as an instance variable
        self.local_search_method = local_search_method
        super().__init__(*args, **kwargs)

    def _register_tools(self):
        if not self.config.tool_names:
            return
        for tool_name in list(set(self.config.tool_names)):
            if tool_name == "local_search":
                self._tools.append(self.local_search())
            elif tool_name == "web_search":
                self._tools.append(self.web_search())
            else:
                raise ValueError(f"Unsupported tool name: {tool_name}")

    def web_search(self) -> Tool:
        return Tool(
            name="web_search",
            description="Search for information on the web - use this tool when the user query needs LIVE or recent data.",
            results_function=self._web_search_function,
            llm_format_function=RAGAgentMixin.format_search_results_for_llm,
            stream_function=RAGAgentMixin.format_search_results_for_stream,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search Google with.",
                    },
                },
                "required": ["query"],
            },
        )

    async def _web_search_function(
        self,
        query: str,
        search_settings: SearchSettings,
        *args,
        **kwargs,
    ) -> AggregateSearchResult:
        from ..utils.serper import SerperClient

        serper_client = SerperClient()
        raw_results = serper_client.get_raw(query)
        web_response = WebSearchResponse.from_serper_results(raw_results)
        return AggregateSearchResult(
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=web_response.organic_results,
        )

    def local_search(self) -> Tool:
        return Tool(
            name="local_search",
            description="Search your local knowledgebase using the R2R AI system",
            results_function=self._local_search_function,
            llm_format_function=RAGAgentMixin.format_search_results_for_llm,
            stream_function=RAGAgentMixin.format_search_results_for_stream,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search the local knowledgebase with.",
                    },
                },
                "required": ["query"],
            },
        )

    async def _local_search_function(
        self,
        query: str,
        search_settings: SearchSettings,
        *args,
        **kwargs,
    ) -> AggregateSearchResult:
        # Use the provided local search method instead of search pipeline
        if not self.local_search_method:
            raise ValueError("Local search method not provided")

        response = await self.local_search_method(
            query=query,
            search_settings=search_settings,
        )

        if isinstance(response, AggregateSearchResult):
            return response

        # If it's a dict, convert the response dict to AggregateSearchResult
        return AggregateSearchResult(
            chunk_search_results=response.get("chunk_search_results", []),
            graph_search_results=response.get("graph_search_results", []),
            web_search_results=None,
        )

    @staticmethod
    def format_search_results_for_stream(
        results: AggregateSearchResult,
    ) -> str:
        return format_search_results_for_stream(results)

    @staticmethod
    def format_search_results_for_llm(
        results: AggregateSearchResult,
    ) -> str:
        return format_search_results_for_llm(results)


class R2RRAGAgent(RAGAgentMixin, R2RAgent):
    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: LiteLLMCompletionProvider | OpenAICompletionProvider,
        config: AgentConfig,
        rag_generation_config: GenerationConfig,
        local_search_method: callable,
    ):
        # Initialize the R2RAgent first
        R2RAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
        )
        # Then initialize the mixin with the local search method
        RAGAgentMixin.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
            local_search_method=local_search_method,
        )


class R2RStreamingRAGAgent(RAGAgentMixin, R2RStreamingAgent):
    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: LiteLLMCompletionProvider | OpenAICompletionProvider,
        config: AgentConfig,
        rag_generation_config: GenerationConfig,
        local_search_method: callable,
    ):
        config.stream = True
        # Initialize the R2RStreamingAgent first
        R2RStreamingAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
        )
        # Then initialize the mixin with the local search method
        RAGAgentMixin.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
            local_search_method=local_search_method,
        )
