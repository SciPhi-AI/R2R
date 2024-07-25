import json
from abc import ABCMeta, abstractmethod
from typing import Any, Optional

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
                print("message = ", message)
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

    async def get_and_process_response(
        self, generation_config: GenerationConfig
    ) -> str:
        stream = self.llm_provider.get_completion_stream(
            self.conversation.get_messages(),
            generation_config,
        )
        return await self.process_llm_response(stream)

    async def process_llm_response(self, stream):
        function_name = None
        function_arguments = ""
        content = ""

        for chunk in stream:
            print("chunk = ", chunk)
            delta = chunk.choices[0].delta

            if delta.function_call:
                if delta.function_call.name:
                    function_name = delta.function_call.name
                if delta.function_call.arguments:
                    function_arguments += delta.function_call.arguments
            elif delta.content:
                content += delta.content

        if function_name:
            return await self.handle_function_call(
                function_name, function_arguments
            )
        else:
            return self.handle_content_response(content)
