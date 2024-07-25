import json
from typing import Any, AsyncGenerator, Optional

from r2r.assistants import R2RAssistant, R2RStreamingAssistant
from r2r.base import (
    AssistantConfig,
    GenerationConfig,
    LLMProvider,
    PromptProvider,
    Tool,
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

    async def asearch(self, query: str) -> str:
        response = await self.search_pipeline.run(to_async_generator([query]))
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

    async def asearch(self, query: str) -> str:
        response = await self.search_pipeline.run(to_async_generator([query]))
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


# import json
# from typing import Any, AsyncGenerator

# from r2r.assistants import R2RAssistant, R2RStreamingAssistant
# from r2r.base import (
#     AssistantConfig,
#     LLMProvider,
#     PromptProvider,
#     Tool,
#     to_async_generator,
# )
# from r2r.pipelines import SearchPipeline


# class RAGAssistant(R2RAssistant):
#     def __init__(
#         self,
#         llm_provider: LLMProvider,
#         prompt_provider: PromptProvider,
#         search_pipeline: SearchPipeline,
#         config: AssistantConfig,
#     ):
#         self.search_pipeline = search_pipeline

#         # Define the search tool using the asearch method
#         search_tool = Tool(
#             name="search",
#             description="Search for information using the R2R framework",
#             function=self.asearch,
#             parameters={
#                 "type": "object",
#                 "properties": {
#                     "query": {
#                         "type": "string",
#                         "description": "The query to search the local vector database with.",
#                     },
#                 },
#                 "required": ["query"],
#             },
#         )

#         # Add the search tool to the config
#         if config.tools is None:
#             config.tools = [search_tool]
#         else:
#             config.tools.append(search_tool)

#         # Call the parent constructor with the updated config
#         super().__init__(llm_provider, prompt_provider, config)

#     async def asearch(self, query: str) -> str:
#         response = await self.search_pipeline.run(to_async_generator([query]))
#         results = ""
#         for i, result in enumerate(response.vector_search_results):
#             text = result.metadata.get("text", "N/A")
#             results += f"{i+1}. {text}\n"
#         return results


# class StreamingRAGAssistant(RAGAssistant):
#     def __init__(
#         self,
#         llm_provider: LLMProvider,
#         prompt_provider: PromptProvider,
#         search_pipeline: SearchPipeline,
#         config: AssistantConfig,
#     ):
#         # Ensure the config is set to stream
#         config.stream = True
#         super().__init__(
#             llm_provider, prompt_provider, search_pipeline, config
#         )

#     async def arun(self, user_message: str) -> AsyncGenerator[str, None]:
#         # Add the user message to the conversation
#         self.add_user_message(user_message)

#         self._completed = False
#         while not self._completed:
#             generation_config_with_functions = self.get_generation_config()

#             async for chunk in self.llm_provider.get_completion_stream(
#                 self.conversation.get_messages(),
#                 generation_config_with_functions,
#             ):
#                 result = await self.process_stream_chunk(chunk)
#                 if result:
#                     yield result

#     async def process_stream_chunk(self, chunk: Any) -> str:
#         delta = chunk.choices[0].delta

#         if delta.function_call:
#             # Accumulate function call information
#             if not hasattr(self, "_current_function_call"):
#                 self._current_function_call = {
#                     "name": delta.function_call.name,
#                     "arguments": "",
#                 }
#             if delta.function_call.arguments:
#                 self._current_function_call[
#                     "arguments"
#                 ] += delta.function_call.arguments

#             # Check if the function call is complete
#             if chunk.choices[0].finish_reason == "function_call":
#                 # Execute the function
#                 function_name = self._current_function_call["name"]
#                 function_args = json.loads(
#                     self._current_function_call["arguments"]
#                 )

#                 self.conversation.create_and_add_message(
#                     "assistant", function_call=self._current_function_call
#                 )

#                 tool_result = await self.execute_tool(
#                     function_name, **function_args
#                 )
#                 self.conversation.create_and_add_message(
#                     "function", content=tool_result, name=function_name
#                 )

#                 # Clear the current function call
#                 del self._current_function_call

#                 # Continue the conversation
#                 return None  # No content to yield for function calls

#         elif delta.content:
#             # For regular content, yield it directly
#             return delta.content

#         # If neither function call nor content, return None
#         return None

#     async def execute_tool(self, tool_name: str, **kwargs) -> str:
#         if tool_name == "search":
#             return await self.asearch(**kwargs)
#         else:
#             return f"Error: Tool {tool_name} not found."

#     def get_generation_config(self):
#         return self.config.generation_config.model_copy(
#             update={
#                 "functions": [
#                     {
#                         "name": tool.name,
#                         "description": tool.description,
#                         "parameters": tool.parameters,
#                     }
#                     for tool in self.tools
#                 ],
#                 "stream": True,
#             }
#         )
