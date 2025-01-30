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

        # Return final content
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
        # Unchanged from your snippet:
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
                # If there are multiple tool_calls, call them sequentially here
                # (Because this is the non-streaming version, concurrency is less critical.)
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

    async def process_llm_response(
        self,
        stream: AsyncGenerator[LLMChatCompletionChunk, None],
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Updated to:
        1) Accumulate interleaved content and tool calls gracefully.
        2) Finalize content even if no tool calls are made.
        3) Support processing of both content and tool calls in parallel.
        """
        pending_tool_calls = {}
        content_buffer = ""
        function_arguments = ""

        inside_thoughts = False
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content and delta.content.count(
                "<Thoughts>"
            ) > delta.content.count("</Thoughts>"):
                inside_thoughts = True
            elif (
                delta.content
                and inside_thoughts
                and delta.content.count("</Thoughts>")
                > delta.content.count("<Thoughts>")
            ):
                inside_thoughts = False
            finish_reason = chunk.choices[0].finish_reason

            # 1) Handle interleaved tool_calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in pending_tool_calls:
                        pending_tool_calls[idx] = {
                            "id": tc.id,  # could be None
                            "name": tc.function.name or "",
                            "arguments": tc.function.arguments or "",
                        }
                    else:
                        # Accumulate partial tool call details
                        if tc.function.name:
                            pending_tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            pending_tool_calls[idx][
                                "arguments"
                            ] += tc.function.arguments
                        # Set the ID if it appears in later chunks
                        if tc.id and not pending_tool_calls[idx]["id"]:
                            pending_tool_calls[idx]["id"] = tc.id

            # 2) Handle partial function_call (single-call logic)
            if delta.function_call:
                if delta.function_call.name:
                    function_name = delta.function_call.name
                if delta.function_call.arguments:
                    function_arguments += delta.function_call.arguments

            # 3) Handle normal content
            elif delta.content:
                content_buffer += delta.content
                yield delta.content

            # 4) Check finish_reason for tool calls
            if finish_reason == "tool_calls":
                # Finalize the tool calls
                calls_list = []
                sorted_indexes = sorted(pending_tool_calls.keys())
                for idx in sorted_indexes:
                    call_info = pending_tool_calls[idx]
                    call_id = call_info["id"] or f"call_{idx}"
                    calls_list.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": call_info["name"],
                                "arguments": call_info["arguments"],
                            },
                        }
                    )

                assistant_msg = Message(
                    role="assistant",
                    content=content_buffer or None,
                    tool_calls=calls_list,
                )
                await self.conversation.add_message(assistant_msg)

                # Execute tool calls in parallel
                for idx, tool_call in pending_tool_calls.items():
                    if inside_thoughts:
                        yield "</Thoughts>"
                    yield "<Thoughts>"
                    yield f"Calling function: {tool_call['name']}, with payload `{tool_call['arguments']}..."
                    yield "</Thoughts>"
                    if inside_thoughts:
                        yield "<Thoughts>"
                async_calls = [
                    self.handle_function_or_tool_call(
                        call_info["name"],
                        call_info["arguments"],
                        tool_id=(call_info["id"] or f"call_{idx}"),
                        *args,
                        **kwargs,
                    )
                    for idx, call_info in pending_tool_calls.items()
                ]
                await asyncio.gather(*async_calls)

                # Clear the tool call state
                pending_tool_calls.clear()
                content_buffer = ""

            elif finish_reason == "stop":
                # Finalize content if streaming stops
                if content_buffer:
                    await self.conversation.add_message(
                        Message(role="assistant", content=content_buffer)
                    )
                elif pending_tool_calls:
                    # TODO - RM COPY PASTA.
                    calls_list = []
                    sorted_indexes = sorted(pending_tool_calls.keys())
                    for idx in sorted_indexes:
                        call_info = pending_tool_calls[idx]
                        call_id = call_info["id"] or f"call_{idx}"
                        calls_list.append(
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": call_info["name"],
                                    "arguments": call_info["arguments"],
                                },
                            }
                        )

                    assistant_msg = Message(
                        role="assistant",
                        content=content_buffer or None,
                        tool_calls=calls_list,
                    )
                    await self.conversation.add_message(assistant_msg)
                    return

                self._completed = True

        # If the stream ends without `finish_reason=stop`
        if not self._completed and content_buffer:
            await self.conversation.add_message(
                Message(role="assistant", content=content_buffer)
            )
            self._completed = True

        # After the stream ends
        if content_buffer and not self._completed:
            await self.conversation.add_message(
                Message(role="assistant", content=content_buffer)
            )
            self._completed = True
