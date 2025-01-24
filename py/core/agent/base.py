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
        Modified to:
         1) Collect partial tool calls in a dict keyed by their .index
         2) Execute them in parallel (asyncio.gather) once finish_reason="tool_calls"
        """
        # Dictionary:
        #   pending_tool_calls[index] = {
        #       "id": str or None,
        #       "name": str,
        #       "arguments": str,
        #   }
        pending_tool_calls = {}

        # For single function_call logic
        function_name = None
        function_arguments = ""

        # Buffer for normal text
        content_buffer = ""

        async for chunk in stream:
            delta = chunk.choices[0].delta

            # 1) Handle partial tool_calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in pending_tool_calls:
                        pending_tool_calls[idx] = {
                            "id": tc.id,  # might be None
                            "name": tc.function.name or "",
                            "arguments": tc.function.arguments or "",
                        }
                    else:
                        # Accumulate partial arguments
                        if tc.function.name:
                            pending_tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            pending_tool_calls[idx][
                                "arguments"
                            ] += tc.function.arguments
                        # If we see an ID on a later chunk, set it now
                        if tc.id and not pending_tool_calls[idx]["id"]:
                            pending_tool_calls[idx]["id"] = tc.id

            # 2) Handle partial function_call
            if delta.function_call:
                if delta.function_call.name:
                    function_name = delta.function_call.name
                if delta.function_call.arguments:
                    function_arguments += delta.function_call.arguments

            # 3) Handle normal text
            elif delta.content:
                if content_buffer == "":
                    yield "<completion>"
                content_buffer += delta.content
                yield delta.content

            # 4) Check finish_reason
            finish_reason = chunk.choices[0].finish_reason

            if finish_reason == "tool_calls":
                # The model has finished specifying this entire set of tool calls in an assistant message.
                if not pending_tool_calls:
                    logger.warning(
                        "Got finish_reason=tool_calls but no pending tool calls."
                    )
                else:
                    # 4a) Build a single 'assistant' message with all tool_calls
                    calls_list = []
                    # Sort by index to ensure consistent ordering
                    sorted_indexes = sorted(pending_tool_calls.keys())
                    for idx in sorted_indexes:
                        call_info = pending_tool_calls[idx]
                        call_id = (
                            call_info["id"]
                            if call_info["id"]
                            else f"call_{idx}"
                        )
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

                    # 4b) Execute them in parallel using asyncio.gather
                    async_calls = []
                    for idx in sorted_indexes:
                        call_info = pending_tool_calls[idx]
                        call_id = call_info["id"] or f"call_{idx}"
                        async_calls.append(
                            self.handle_function_or_tool_call(
                                call_info["name"],
                                call_info["arguments"],
                                tool_id=call_id,
                                *args,
                                **kwargs,
                            )
                        )
                    results = await asyncio.gather(*async_calls)

                    # 4c) Now yield the <tool_call> blocks in the same order
                    for idx, tool_result in zip(sorted_indexes, results):
                        # We re-lookup the name, arguments, id
                        call_info = pending_tool_calls[idx]
                        call_id = call_info["id"] or f"call_{idx}"
                        call_name = call_info["name"]
                        call_args = call_info["arguments"]

                        yield "<tool_call>"
                        yield f"<name>{call_name}</name>"
                        yield f"<arguments>{call_args}</arguments>"

                        if tool_result.stream_result:
                            yield f"<results>{tool_result.stream_result}</results>"
                        else:
                            yield f"<results>{tool_result.llm_formatted_result}</results>"

                        yield "</tool_call>"

                        # 4d) Add a role="function" message
                        await self.conversation.add_message(
                            Message(
                                role="function",
                                name=call_id,
                                content=tool_result.llm_formatted_result,
                            )
                        )

                    # 4e) Reset
                    pending_tool_calls.clear()
                    content_buffer = ""

            elif finish_reason == "function_call":
                # Single function call approach
                if not function_name:
                    logger.info("Function name not found in function call.")
                    continue

                # Add the assistant message with function_call
                assistant_msg = Message(
                    role="assistant",
                    content=content_buffer if content_buffer else None,
                    function_call={
                        "name": function_name,
                        "arguments": function_arguments,
                    },
                )
                await self.conversation.add_message(assistant_msg)

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

                # Add a function-role message
                await self.conversation.add_message(
                    Message(
                        role="function",
                        name=function_name,
                        content=tool_result.llm_formatted_result,
                    )
                )

                function_name = None
                function_arguments = ""
                content_buffer = ""

            elif finish_reason == "stop":
                # The model is done producing text
                if content_buffer:
                    await self.conversation.add_message(
                        Message(role="assistant", content=content_buffer)
                    )
                self._completed = True
                yield "</completion>"

        # After the stream ends
        if content_buffer and not self._completed:
            await self.conversation.add_message(
                Message(role="assistant", content=content_buffer)
            )
            self._completed = True
            yield "</completion>"
