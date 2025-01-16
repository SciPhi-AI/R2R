import asyncio
import logging
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

logger = logging.getLogger()


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
        self._reset()

    def _reset(self):
        self._completed = False
        self.conversation = Conversation()

    @syncable
    async def arun(
        self,
        messages: list[Message],
        system_instruction: Optional[str] = None,
        *args,
        **kwargs,
    ) -> list[dict]:
        # TODO - Make this method return a list of messages.
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

        # Get the output messages
        all_messages: list[dict] = await self.conversation.get_messages()
        all_messages.reverse()

        output_messages = []
        for message_2 in all_messages:
            if (
                message_2.get("content")
                and message_2.get("content") != messages[-1].content
            ):
                output_messages.append(message_2)
            else:
                break
        output_messages.reverse()

        return output_messages

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
            stream = self.llm_provider.aget_completion_stream(
                messages_list,
                generation_config,
            )
            async for proc_chunk in self.process_llm_response(
                stream, *args, **kwargs
            ):
                yield proc_chunk

    def run(
        self, system_instruction, messages, *args, **kwargs
    ) -> Generator[str, None, None]:
        return sync_wrapper(
            self.arun(system_instruction, messages, *args, **kwargs)
        )

    async def process_llm_response(  # type: ignore
        self,
        stream: AsyncGenerator[LLMChatCompletionChunk, None],
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        function_name = None
        function_arguments = ""
        current_tool_name = None
        current_tool_arguments = ""
        current_tool_call_id = None
        content_buffer = ""

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.tool_calls:
                # It's possible to get multiple tool calls in the same chunk,
                # but usually you'll see them one at a time. 
                for tool_call in delta.tool_calls:
                    # If tool_call.function.name is present, store/overwrite
                    if tool_call.function.name:
                        current_tool_name = tool_call.function.name
                    # If tool_call.id is present, store
                    if tool_call.id:
                        current_tool_call_id = tool_call.id
                    # If tool_call.function.arguments is present, append
                    if tool_call.function.arguments:
                        current_tool_arguments += tool_call.function.arguments


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
            finish_reason = chunk.choices[0].finish_reason
            if finish_reason == "tool_calls":
                print('current_tool_call_id = ', current_tool_call_id)
                # We have the full name + arguments now, so let's "call" the tool
                if current_tool_name:
                    yield "<tool_call>"
                    yield f"<name>{current_tool_name}</name>"
                    yield f"<arguments>{current_tool_arguments}</arguments>"
                    print('args = ', args)
                    print('kweargs = ', kwargs)
                    tool_result = await self.handle_function_or_tool_call(
                        current_tool_name,
                        current_tool_arguments,
                        tool_id=current_tool_call_id,
                        *args, **kwargs,
                    )
                    if tool_result.stream_result:
                        yield f"<results>{tool_result.stream_result}</results>"
                    else:
                        yield f"<results>{tool_result.llm_formatted_result}</results>"

                    yield "</tool_call>"

                    # Reset for next call
                    current_tool_name = None
                    current_tool_arguments = ""
                    current_tool_call_id = None
                else:
                    logger.warning(
                        "Got finish_reason=tool_calls but no tool name was ever set."
                    )
            elif finish_reason == "function_call":
                if not function_name:
                    logger.info("Function name not found in function call.")
                    continue

                yield "<function_call>"
                yield f"<name>{function_name}</name>"
                yield f"<arguments>{function_arguments}</arguments>"
                print('args = ', args)
                print('kweargs = ', kwargs)

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

            elif chunk.choices[0].finish_reason == "stop":
                if content_buffer:
                    await self.conversation.add_message(
                        Message(role="assistant", content=content_buffer)
                    )
                self._completed = True
                yield "</completion>"

        # Handle any remaining content after the stream ends
        if content_buffer and not self._completed:
            await self.conversation.add_message(
                Message(role="assistant", content=content_buffer)
            )
            self._completed = True
            yield "</completion>"
