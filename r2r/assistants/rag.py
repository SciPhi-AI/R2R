from r2r.assistants import R2RAssistant, R2RStreamingAssistant
from r2r.base import (
    AssistantConfig,
    KGSearchSettings,
    LLMProvider,
    PromptProvider,
    Tool,
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
            function=self.asearch,
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
    ) -> str:
        response = await self.search_pipeline.run(
            to_async_generator([query]),
            vector_search_settings=vector_search_settings,
        )
        results = ""
        for i, result in enumerate(response.vector_search_results):
            text = result.metadata.get("text", "N/A")
            results += f"{i+1}. {text}\n"
        return results


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
