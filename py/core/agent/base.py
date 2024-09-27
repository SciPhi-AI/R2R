import asyncio
from abc import ABCMeta
from typing import AsyncGenerator, Generator, Optional

from core.base.abstractions import (
    AsyncSyncMeta,
    LLMChatCompletion,
    LLMChatCompletionChunk,
    Message,
    syncable,
)
from core.base.agent import Agent, Conversation


class CombinedMeta(AsyncSyncMeta, ABCMeta):
    pass


def sync_wrapper(async_gen):
    loop = asyncio.get_event_loop()

    def wrapper():
        try:
            while True:
                try:
                    yield loop.run_until_complete(async_gen.__anext__())
                except StopAsyncIteration:
                    break
        finally:
            loop.run_until_complete(async_gen.aclose())

    return wrapper()


class R2RAgent(Agent, metaclass=CombinedMeta):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._register_tools()
        self._reset()

    def _reset(self):
        self._completed = False
        self.conversation = Conversation()

    @syncable
    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> list[dict]:
        self._reset()
        await self._setup(system_instruction)

        if messages:
            for message in messages:
                await self.conversation.add_message(message)

        while not self._completed:
            messages_list = await self.conversation.get_messages()
            generation_config = self.get_generation_config(messages_list[-1])
            response = await self.llm_provider.aget_completion(
                messages_list,
                generation_config,
            )
            await self.process_llm_response(response, *args, **kwargs)

        return await self.conversation.get_messages()

    async def process_llm_response(
        self, response: LLMChatCompletion, *args, **kwargs
    ) -> None:
        if not self._completed:
            message = response.choices[0].message
            if message.function_call:
                await self.handle_function_or_tool_call(
                    message.function_call.name,
                    message.function_call.arguments,
                    *args,
                    **kwargs,
                )
            elif message.tool_calls:
                for tool_call in message.tool_calls:
                    await self.handle_function_or_tool_call(
                        tool_call.function.name,
                        tool_call.function.arguments,
                        *args,
                        **kwargs,
                    )
            else:
                await self.conversation.add_message(
                    Message(role="assistant", content=message.content)
                )
                self._completed = True


class R2RStreamingAgent(R2RAgent):
    async def arun(  # type: ignore
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        self._reset()
        await self._setup(system_instruction)

        if messages:
            for message in messages:
                await self.conversation.add_message(message)

        while not self._completed:
            messages_list = await self.conversation.get_messages()

            generation_config = self.get_generation_config(
                messages_list[-1], stream=True
            )
            stream = self.llm_provider.get_completion_stream(
                messages_list,
                generation_config,
            )
            async for chunk in self.process_llm_response(
                stream, *args, **kwargs
            ):
                yield chunk

    def run(
        self, system_instruction, messages, *args, **kwargs
    ) -> Generator[str, None, None]:
        return sync_wrapper(
            self.arun(system_instruction, messages, *args, **kwargs)
        )

    async def process_llm_response(  # type: ignore
        self,
        stream: Generator[LLMChatCompletionChunk, None, None],
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        function_name = None
        function_arguments = ""
        content_buffer = ""

        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    if not tool_call.function:
                        raise ValueError(
                            "Tool function not found in tool call."
                        )
                    name = tool_call.function.name
                    if not name:
                        raise ValueError("Tool name not found in tool call.")
                    arguments = tool_call.function.arguments
                    if not arguments:
                        raise ValueError(
                            "Tool arguments not found in tool call."
                        )

                    results = await self.handle_function_or_tool_call(
                        name,
                        arguments,
                        # FIXME: tool_call.id,
                        *args,
                        **kwargs,
                    )

                    yield "<tool_call>"
                    yield f"<name>{name}</name>"
                    yield f"<arguments>{arguments}</arguments>"
                    yield f"<results>{results}</results>"
                    yield "</tool_call>"

            if delta.function_call:
                if delta.function_call.name:
                    function_name = delta.function_call.name
                if delta.function_call.arguments:
                    function_arguments += delta.function_call.arguments
            elif delta.content:
                if content_buffer == "":
                    yield "<completion>"
                content_buffer += delta.content
                yield delta.content

            if chunk.choices[0].finish_reason == "function_call":
                if not function_name:
                    raise ValueError(
                        "Function name not found in function call."
                    )

                yield "<function_call>"
                yield f"<name>{function_name}</name>"
                yield f"<arguments>{function_arguments}</arguments>"
                tool_result = await self.handle_function_or_tool_call(
                    function_name, function_arguments, *args, **kwargs
                )
                if tool_result.stream_result:
                    yield f"<results>{tool_result.stream_result}</results>"
                else:
                    yield f"<results>{tool_result.llm_formatted_result}</results>"

                yield "</function_call>"

                function_name = None
                function_arguments = ""

                self.arun(*args, **kwargs)

            elif chunk.choices[0].finish_reason == "stop":
                if content_buffer:
                    await self.conversation.add_message(
                        Message(role="assistant", content=content_buffer)
                    )
                self._completed = True
                yield "</completion>"
