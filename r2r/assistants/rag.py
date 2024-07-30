import json

from r2r.assistants import R2RAssistant, R2RStreamingAssistant
from r2r.base import (
    AssistantConfig,
    KGSearchSettings,
    LLMProvider,
    PromptProvider,
    Tool,
    VectorSearchResult,
    VectorSearchSettings,
    to_async_generator,
)
from r2r.pipelines import SearchPipeline


class RAGAssistantMixin:
    def __init__(self, search_pipeline: SearchPipeline, *args, **kwargs):
        self.search_pipeline = search_pipeline
        super().__init__(*args, **kwargs)
        self.add_search_tool()

    def add_search_tool(self):
        search_tool = Tool(
            name="search",
            description="Search for information using the R2R framework",
            results_function=self.asearch,
            llm_format_function=RAGAssistantMixin.format_search_results_for_llm,
            stream_function=RAGAssistantMixin.format_search_results_for_stream,
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
        if search_tool.name not in [tool.name for tool in self.config.tools]:
            self.config.tools.append(search_tool)

    async def asearch(
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
        )
        return response.vector_search_results

    @staticmethod
    def format_search_results_for_llm(
        results: list[VectorSearchResult],
    ) -> str:
        formatted_results = ""
        for i, result in enumerate(results):
            text = result.metadata.get("text", "N/A")
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


class R2RRAGAssistant(RAGAssistantMixin, R2RAssistant):
    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        search_pipeline: SearchPipeline,
        config: AssistantConfig,
    ):
        super().__init__(
            search_pipeline=search_pipeline,
            llm_provider=llm_provider,
            prompt_provider=prompt_provider,
            config=config,
        )


class R2RStreamingRAGAssistant(RAGAssistantMixin, R2RStreamingAssistant):
    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        search_pipeline: SearchPipeline,
        config: AssistantConfig,
    ):
        config.stream = True
        super().__init__(
            search_pipeline=search_pipeline,
            llm_provider=llm_provider,
            prompt_provider=prompt_provider,
            config=config,
        )
