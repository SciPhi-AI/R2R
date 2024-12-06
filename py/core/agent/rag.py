from typing import Union

from core.agent import R2RAgent, R2RStreamingAgent
from core.base import (
    format_search_results_for_llm,
    format_search_results_for_stream,
)
from core.base.abstractions import (
    AggregateSearchResult,
    GraphSearchSettings,
    SearchSettings,
    WebSearchResponse,
)
from core.base.agent import AgentConfig, Tool
from core.base.providers import CompletionProvider
from core.base.utils import to_async_generator
from core.pipelines import SearchPipeline
from core.providers import (
    LiteLLMCompletionProvider,
    OpenAICompletionProvider,
    PostgresDBProvider,
)


class RAGAgentMixin:
    def __init__(self, search_pipeline: SearchPipeline, *args, **kwargs):
        self.search_pipeline = search_pipeline
        super().__init__(*args, **kwargs)

    def _register_tools(self):
        if not self.config.tool_names:
            return
        for tool_name in self.config.tool_names:
            if tool_name == "local_search":
                self._tools.append(self.local_search())
            elif tool_name == "web_search":
                self._tools.append(self.web_search())
            else:
                raise ValueError(f"Unsupported tool name: {tool_name}")

    def web_search(self) -> Tool:
        return Tool(
            name="web_search",
            description="Search for information on the web.",
            results_function=self._web_search,
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

    async def _web_search(
        self,
        query: str,
        search_settings: SearchSettings,
        *args,
        **kwargs,
    ) -> list[AggregateSearchResult]:
        from .serper import SerperClient

        serper_client = SerperClient()
        # TODO - make async!
        # TODO - Move to search pipeline, make configurable.
        raw_results = serper_client.get_raw(query)
        web_response = WebSearchResponse.from_serper_results(raw_results)
        return AggregateSearchResult(
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=web_response.organic_results,  # TODO - How do we feel about throwing away so much info?
        )

    def local_search(self) -> Tool:
        return Tool(
            name="local_search",
            description="Search your local knowledgebase using the R2R AI system",
            results_function=self._local_search,
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

    async def _local_search(
        self,
        query: str,
        search_settings: SearchSettings,
        *args,
        **kwargs,
    ) -> list[AggregateSearchResult]:
        response = await self.search_pipeline.run(
            to_async_generator([query]),
            state=None,
            search_settings=search_settings,
        )
        return response

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
        database_provider: PostgresDBProvider,
        llm_provider: Union[
            LiteLLMCompletionProvider, OpenAICompletionProvider
        ],
        search_pipeline: SearchPipeline,
        config: AgentConfig,
    ):
        super().__init__(
            database_provider=database_provider,
            search_pipeline=search_pipeline,
            llm_provider=llm_provider,
            config=config,
        )


class R2RStreamingRAGAgent(RAGAgentMixin, R2RStreamingAgent):
    def __init__(
        self,
        database_provider: PostgresDBProvider,
        llm_provider: Union[
            LiteLLMCompletionProvider, OpenAICompletionProvider
        ],
        search_pipeline: SearchPipeline,
        config: AgentConfig,
    ):
        config.stream = True
        super().__init__(
            database_provider=database_provider,
            search_pipeline=search_pipeline,
            llm_provider=llm_provider,
            config=config,
        )
