import json

from core.agent import R2RAgent, R2RStreamingAgent
from core.base.abstractions import (
    KGSearchSettings,
    VectorSearchResult,
    VectorSearchSettings,
)
from core.base.agent import AgentConfig, Tool
from core.base.providers import CompletionProvider, PromptProvider
from core.base.utils import to_async_generator
from core.pipelines import SearchPipeline


class RAGAgentMixin:
    def __init__(self, search_pipeline: SearchPipeline, *args, **kwargs):
        self.search_pipeline = search_pipeline
        super().__init__(*args, **kwargs)

    def _register_tools(self):
        if not self.config.tool_names:
            return
        for tool_name in self.config.tool_names:
            if tool_name == "search":
                self._tools.append(self.search_tool())
            else:
                raise ValueError(f"Unsupported tool name: {tool_name}")

    def search_tool(self) -> Tool:
        return Tool(
            name="search",
            description="Search for information using the R2R framework",
            results_function=self.search,
            llm_format_function=RAGAgentMixin.format_search_results_for_llm,
            stream_function=RAGAgentMixin.format_search_results_for_stream,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search the local vector database with.",
                    },
                },
                "required": ["query"],
            },
        )

    async def search(
        self,
        query: str,
        vector_search_settings: VectorSearchSettings,
        kg_search_settings: KGSearchSettings,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        response = await self.search_pipeline.run(
            to_async_generator([query]),
            vector_search_settings=vector_search_settings,
            kg_search_settings=kg_search_settings,
        )
        return response.vector_search_results

    @staticmethod
    def format_search_results_for_llm(
        results: list[VectorSearchResult],
    ) -> str:
        formatted_results = ""
        for i, result in enumerate(results):
            text = result.text
            formatted_results += f"{i+1}. {text}\n"
        return formatted_results

    @staticmethod
    def format_search_results_for_stream(
        results: list[VectorSearchResult],
    ) -> str:
        formatted_result = ",".join(
            [json.dumps(result.json()) for result in results]
        )
        return formatted_result


class R2RRAGAgent(RAGAgentMixin, R2RAgent):
    def __init__(
        self,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        search_pipeline: SearchPipeline,
        config: AgentConfig,
    ):
        super().__init__(
            search_pipeline=search_pipeline,
            llm_provider=llm_provider,
            prompt_provider=prompt_provider,
            config=config,
        )


class R2RStreamingRAGAgent(RAGAgentMixin, R2RStreamingAgent):
    def __init__(
        self,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        search_pipeline: SearchPipeline,
        config: AgentConfig,
    ):
        config.stream = True
        super().__init__(
            search_pipeline=search_pipeline,
            llm_provider=llm_provider,
            prompt_provider=prompt_provider,
            config=config,
        )
