import json
from abc import ABCMeta, abstractmethod
from typing import Any, AsyncGenerator, Generator, Optional

from r2r.base import (
    Assistant,
    AsyncSyncMeta,
    GenerationConfig,
    LLMChatCompletion,
    Message,
    VectorSearchSettings,
    syncable,
)


class CombinedMeta(AsyncSyncMeta, ABCMeta):
    pass


class BaseR2RAssistant(Assistant, metaclass=CombinedMeta):

    @syncable
    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        *args,
        **kwargs,
    ) -> list[LLMChatCompletion]:
        messages_have_system_instruction = not (
            messages and "system" in messages
        )
        if system_instruction or messages_have_system_instruction:
            self._completed = False
            self._setup(system_instruction)

        if messages:
            for message in messages:
                self.conversation.add_message(message)

        while not self._completed:
            generation_config_with_functions = self.get_generation_config()
            await self.get_and_process_response(
                generation_config_with_functions, vector_search_settings
            )

        return self.conversation.messages

    def get_generation_config(self) -> GenerationConfig:
        return GenerationConfig(
            **self.config.generation_config.model_dump(
                exclude={"functions", "stream"},
            ),
            functions=[
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
                for tool in self.tools
            ],
            stream=self.is_streaming(),
        )

    @abstractmethod
    async def get_and_process_response(
        self, generation_config: GenerationConfig
    ) -> str:
        pass

    @abstractmethod
    def is_streaming(self) -> bool:
        pass

    async def handle_function_call(
        self,
        function_name: str,
        function_arguments: str,
        vector_search_settings: VectorSearchSettings,
    ) -> str:

        tool_args = json.loads(function_arguments)
        self.conversation.create_and_add_message(
            "assistant",
            function_call={
                "name": function_name,
                "arguments": function_arguments,
            },
        )

        if function_name == "search":
            tool_result = await self.asearch(
                **tool_args, vector_search_settings=vector_search_settings
            )
        else:
            tool_result = await self.execute_tool(function_name, **tool_args)

        self.conversation.create_and_add_message(
            "function", content=tool_result, name=function_name
        )
        return await self.arun()  # Continue the conversation

    def handle_content_response(
        self, response: LLMChatCompletion
    ) -> LLMChatCompletion:
        self.conversation.create_and_add_message(
            "assistant", content=response.choices[0].message.content
        )
        self._completed = True
        return response


class R2RAssistant(BaseR2RAssistant):
    def is_streaming(self) -> bool:
        return False

    async def get_and_process_response(
        self,
        generation_config: GenerationConfig,
        vector_search_settings: VectorSearchSettings,
    ) -> str:
        print("conversation:", self.conversation.get_messages())
        response = await self.llm_provider.aget_completion(
            self.conversation.get_messages(),
            generation_config,
        )
        print("response:", response)
        return await self.process_llm_response(
            response, vector_search_settings
        )

    async def process_llm_response(
        self,
        response: dict[str, Any],
        vector_search_settings: VectorSearchSettings,
    ) -> str:
        message = response.choices[0].message
        if message.function_call:
            return await self.handle_function_call(
                message.function_call.name,
                message.function_call.arguments,
                vector_search_settings,
            )
        else:
            return self.handle_content_response(response)


class R2RStreamingAssistant(BaseR2RAssistant):
    def is_streaming(self) -> bool:
        return True

    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        *args,
        **kwargs,
    ) -> AsyncGenerator[LLMChatCompletion, None]:
        messages_have_system_instruction = not (
            messages and "system" in messages
        )
        if system_instruction or messages_have_system_instruction:
            self._completed = False
            self._setup(system_instruction)

        if messages:
            for message in messages:
                self.conversation.add_message(message)

        while not self._completed:
            generation_config_with_functions = self.get_generation_config()
            async for chunk in await self.get_and_process_response(
                generation_config_with_functions, vector_search_settings
            ):
                yield chunk

    async def get_and_process_response(
        self,
        generation_config: GenerationConfig,
        vector_search_settings: VectorSearchSettings,
    ) -> AsyncGenerator[str, None]:
        stream = self.llm_provider.get_completion_stream(
            self.conversation.get_messages(),
            generation_config,
        )
        return self.process_llm_response(stream, vector_search_settings)

    async def process_llm_response(
        self, stream, vector_search_settings: VectorSearchSettings
    ) -> AsyncGenerator[str, None]:
        function_name = None
        function_arguments = ""
        content_buffer = ""

        async for chunk in self._iterate_stream(stream):
            delta = chunk.choices[0].delta

            if delta.function_call:
                if delta.function_call.name:
                    function_name = delta.function_call.name
                if delta.function_call.arguments:
                    function_arguments += delta.function_call.arguments
            elif delta.content:
                content_buffer += delta.content
                yield delta.content

            if chunk.choices[0].finish_reason == "function_call":
                async for result in self.handle_function_call(
                    function_name, function_arguments, vector_search_settings
                ):
                    yield result
                function_name = None
                function_arguments = ""

            elif chunk.choices[0].finish_reason == "stop":
                if content_buffer:
                    self.handle_content_response(content_buffer)
                self._completed = True

    async def _iterate_stream(self, stream):
        if hasattr(stream, "__aiter__"):
            async for chunk in stream:
                yield chunk
        else:
            for chunk in stream:
                yield chunk

    async def handle_function_call(
        self,
        function_name: str,
        function_arguments: str,
        vector_search_settings: VectorSearchSettings,
    ) -> AsyncGenerator[str, None]:
        tool_args = json.loads(function_arguments)
        self.conversation.create_and_add_message(
            "assistant",
            function_call={
                "name": function_name,
                "arguments": function_arguments,
            },
        )
        if function_name == "search":
            tool_result = await self.asearch(
                **tool_args, vector_search_settings=vector_search_settings
            )
        else:
            tool_result = await self.execute_tool(function_name, **tool_args)

        self.conversation.create_and_add_message(
            "function", content=tool_result, name=function_name
        )
        yield tool_result

    def handle_content_response(self, content: str) -> None:
        self.conversation.create_and_add_message("assistant", content=content)

    # async def get_and_process_response(
    #     self, generation_config: GenerationConfig, vector_search_settings: VectorSearchSettings
    # ) -> AsyncGenerator[LLMChatCompletion, None]:
    #     stream = self.llm_provider.get_completion_stream(
    #         self.conversation.get_messages(),
    #         generation_config,
    #     )

    #     # Check if the stream is an async generator or a regular generator
    #     if hasattr(stream, '__aiter__'):
    #         # It's an async generator, we can use it directly
    #         async for chunk in stream:
    #             yield from self.process_llm_response(chunk, vector_search_settings)
    #     else:
    #         # It's a regular generator, we need to wrap it
    #         for chunk in stream:
    #             yield from self.process_llm_response(chunk, vector_search_settings)

    # # async def get_and_process_response(
    # #     self, generation_config: GenerationConfig, vector_search_settings: VectorSearchSettings
    # # ) -> AsyncGenerator[LLMChatCompletion, None]:
    # #     stream = self.llm_provider.get_completion_stream(
    # #         self.conversation.get_messages(),
    # #         generation_config,
    # #     )
    # #     for chunk in stream:
    # #         yield chunk

    # async def process_llm_response(self, stream: AsyncGenerator[LLMChatCompletion, None], vector_search_settings: VectorSearchSettings) -> AsyncGenerator[LLMChatCompletion, None]:
    #     function_name = None
    #     function_arguments = ""
    #     content_buffer = ""

    #     async for chunk in stream:
    #         delta = chunk.choices[0].delta

    #         if delta.function_call:
    #             if delta.function_call.name:
    #                 function_name = delta.function_call.name
    #             if delta.function_call.arguments:
    #                 function_arguments += delta.function_call.arguments
    #         elif delta.content:
    #             content_buffer += delta.content
    #             yield chunk

    #         if chunk.choices[0].finish_reason == "function_call":
    #             await self.handle_function_call(
    #                 function_name, function_arguments, vector_search_settings=vector_search_settings
    #             )
    #             function_name = None
    #             function_arguments = ""

    #         elif chunk.choices[0].finish_reason == "stop":
    #             if content_buffer:
    #                 self.handle_content_response(content_buffer)
    #             self._completed = True

    # async def handle_function_call(
    #     self, function_name: str, function_arguments: str, vector_search_settings: VectorSearchSettings
    # ) -> None:
    #     tool_args = json.loads(function_arguments)
    #     self.conversation.create_and_add_message(
    #         "assistant",
    #         function_call={
    #             "name": function_name,
    #             "arguments": function_arguments,
    #         },
    #     )
    #     if function_name == "search":
    #         tool_result = await self.asearch(**tool_args, vector_search_settings=vector_search_settings)
    #     else:
    #         tool_result = await self.execute_tool(function_name, **tool_args)

    #     self.conversation.create_and_add_message(
    #         "function", content=tool_result, name=function_name
    #     )
    #     # We don't return or yield anything here, as we'll continue the conversation in the main loop

    # def handle_content_response(self, content: str) -> None:
    #     self.conversation.create_and_add_message("assistant", content=content)


# class R2RStreamingAssistant(BaseR2RAssistant):
#     def is_streaming(self) -> bool:
#         return True

#     async def arun(
#         self,
#         system_instruction: Optional[str] = None,
#         messages: Optional[list[Message]] = None,
#         vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
#         *args,
#         **kwargs,
#     ) -> AsyncGenerator[str, None]:
#         messages_have_system_instruction = not (
#             messages and "system" in messages
#         )
#         if system_instruction or messages_have_system_instruction:
#             self._completed = False
#             self._setup(system_instruction)

#         if messages:
#             for message in messages:
#                 self.conversation.add_message(message)

#         while not self._completed:
#             generation_config_with_functions = self.get_generation_config()
#             async for chunk in self.get_and_process_response(
#                 generation_config_with_functions, vector_search_settings
#             ):
#                 yield chunk

#     def run(self, *args, **kwargs) -> AsyncGenerator[str, None]:
#         return self.arun(*args, **kwargs)

#     async def get_and_process_response(
#         self, generation_config: GenerationConfig, vector_search_settings: VectorSearchSettings
#     ) -> Generator[str, None, None]:
#         stream = self.llm_provider.get_completion_stream(
#             self.conversation.get_messages(),
#             generation_config,
#         )
#         async for chunk in self.process_llm_response(stream, vector_search_settings):
#             yield chunk

#     async def process_llm_response(self, stream: bool, vector_search_settings: VectorSearchSettings) -> Generator[str, None, None]:
#         function_name = None
#         function_arguments = ""
#         content_buffer = ""

#         for chunk in stream:
#             delta = chunk.choices[0].delta

#             if delta.function_call:
#                 if delta.function_call.name:
#                     function_name = delta.function_call.name
#                 if delta.function_call.arguments:
#                     function_arguments += delta.function_call.arguments
#             elif delta.content:
#                 content_buffer += delta.content
#                 yield delta.content

#             if chunk.choices[0].finish_reason == "function_call":
#                 tool_result = await self.handle_function_call(
#                     function_name, function_arguments, vector_search_settings=vector_search_settings
#                 )
#                 function_name = None
#                 function_arguments = ""

#             elif chunk.choices[0].finish_reason == "stop":
#                 if content_buffer:
#                     self.handle_content_response(content_buffer)
#                 self._completed = True

#     # async def handle_function_call(
#     #     self, function_name: str, function_arguments: str, vector_search_settings: VectorSearchSettings
#     # ) -> str:
#     #     tool_args = json.loads(function_arguments)
#     #     self.conversation.create_and_add_message(
#     #         "assistant",
#     #         function_call={
#     #             "name": function_name,
#     #             "arguments": function_arguments,
#     #         },
#     #     )
#     #     if function_name == "search":
#     #         tool_result = await self.asearch(**tool_args, vector_search_settings=vector_search_settings)
#     #     else:
#     #         tool_result = await self.execute_tool(function_name, **tool_args)

#     #     self.conversation.create_and_add_message(
#     #         "function", content=tool_result, name=function_name
#     #     )
#     #     return tool_result

#     def handle_content_response(self, content: str) -> None:
#         self.conversation.create_and_add_message("assistant", content=content)
