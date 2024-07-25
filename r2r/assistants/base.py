import json
from abc import ABCMeta, abstractmethod
from typing import Any, AsyncGenerator, Generator, Optional

from r2r.base import (
    Assistant,
    AsyncSyncMeta,
    GenerationConfig,
    Message,
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
    ) -> str:
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
            result = await self.get_and_process_response(
                generation_config_with_functions
            )

            if self._completed:
                return result

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
        self, function_name: str, function_arguments: str
    ) -> str:
        tool_args = json.loads(function_arguments)
        self.conversation.create_and_add_message(
            "assistant",
            function_call={
                "name": function_name,
                "arguments": function_arguments,
            },
        )
        tool_result = await self.execute_tool(function_name, **tool_args)
        self.conversation.create_and_add_message(
            "function", content=tool_result, name=function_name
        )
        return await self.arun()  # Continue the conversation

    def handle_content_response(self, content: str) -> str:
        self.conversation.create_and_add_message("assistant", content=content)
        self._completed = True
        return content


class R2RAssistant(BaseR2RAssistant):
    def is_streaming(self) -> bool:
        return False

    async def get_and_process_response(
        self, generation_config: GenerationConfig
    ) -> str:
        response = await self.llm_provider.aget_completion(
            self.conversation.get_messages(),
            generation_config,
        )
        return await self.process_llm_response(response)

    async def process_llm_response(self, response: dict[str, Any]) -> str:
        message = response.choices[0].message
        if message.function_call:
            return await self.handle_function_call(
                message.function_call.name, message.function_call.arguments
            )
        else:
            return self.handle_content_response(message.content)


class R2RStreamingAssistant(BaseR2RAssistant):
    def is_streaming(self) -> bool:
        return True

    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
    ) -> AsyncGenerator[str, None]:
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
            async for chunk in self.get_and_process_response(
                generation_config_with_functions
            ):
                yield chunk

    def run(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        return self.arun(*args, **kwargs)

    async def get_and_process_response(
        self, generation_config: GenerationConfig
    ) -> Generator[str, None, None]:
        stream = self.llm_provider.get_completion_stream(
            self.conversation.get_messages(),
            generation_config,
        )
        async for chunk in self.process_llm_response(stream):
            yield chunk

    async def process_llm_response(self, stream) -> Generator[str, None, None]:
        function_name = None
        function_arguments = ""
        content_buffer = ""

        for chunk in stream:
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
                tool_result = await self.handle_function_call(
                    function_name, function_arguments
                )
                function_name = None
                function_arguments = ""

            elif chunk.choices[0].finish_reason == "stop":
                if content_buffer:
                    self.handle_content_response(content_buffer)
                self._completed = True

    async def handle_function_call(
        self, function_name: str, function_arguments: str
    ) -> str:
        tool_args = json.loads(function_arguments)
        self.conversation.create_and_add_message(
            "assistant",
            function_call={
                "name": function_name,
                "arguments": function_arguments,
            },
        )
        tool_result = await self.execute_tool(function_name, **tool_args)
        self.conversation.create_and_add_message(
            "function", content=tool_result, name=function_name
        )
        return tool_result

    def handle_content_response(self, content: str) -> None:
        self.conversation.create_and_add_message("assistant", content=content)
