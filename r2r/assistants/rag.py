from r2r.assistants import R2RAssistant, R2RStreamingAssistant
from r2r.base import (
    AssistantConfig,
    GenerationConfig,
    LLMProvider,
    PromptProvider,
    Tool,
    VectorSearchSettings,
    to_async_generator,
)
from r2r.pipelines import SearchPipeline


class RAGAssistant(R2RAssistant):
    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        search_pipeline: SearchPipeline,
        config: AssistantConfig,
    ):
        self.search_pipeline = search_pipeline

        # Define the search tool using the asearch method
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

        # Add the search tool to the config
        if config.tools is None:
            config.tools = [search_tool]
        else:
            config.tools.append(search_tool)

        # Call the parent constructor with the updated config
        super().__init__(llm_provider, prompt_provider, config)

    async def asearch(
        self, query: str, vector_search_settings: VectorSearchSettings
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


class StreamingRAGAssistant(R2RStreamingAssistant):
    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        search_pipeline: SearchPipeline,
        config: AssistantConfig,
    ):
        self.search_pipeline = search_pipeline

        # Define the search tool using the asearch method
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

        # Add the search tool to the config
        if config.tools is None:
            config.tools = [search_tool]
        else:
            config.tools.append(search_tool)

        # Ensure the config is set to stream
        config.stream = True
        super().__init__(llm_provider, prompt_provider, config)

    async def asearch(
        self, query: str, vector_search_settings: VectorSearchSettings
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

    async def execute_tool(self, tool_name: str, **kwargs) -> str:
        if tool_name == "search":
            return await self.asearch(**kwargs)
        else:
            return f"Error: Tool {tool_name} not found."

    def get_generation_config(self) -> GenerationConfig:
        return self.config.generation_config.model_copy(
            update={
                "functions": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                    for tool in self.tools
                ],
                "stream": True,
            }
        )
