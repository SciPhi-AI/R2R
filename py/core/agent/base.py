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

            if message.tool_calls:
                # import pdb; pdb.set_trace()
                assistant_msg = Message(
                    role="assistant",
                    content=None,
                    tool_calls=[msg.dict() for msg in message.tool_calls],
                )
                await self.conversation.add_message(assistant_msg)

                # If there are multiple tool_calls, call them sequentially here
                # (Because this is the non-streaming version, concurrency is less critical.)
                for tool_call in message.tool_calls:
                    await self.handle_function_or_tool_call(
                        tool_call.function.name,
                        tool_call.function.arguments,
                        tool_id=tool_call.id,
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

        async for chunk in stream:
            delta = chunk.choices[0].delta
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
                if not content_buffer:
                    yield "<completion>"
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
                results = await asyncio.gather(*async_calls)

                # Yield tool call results
                for idx, tool_result in zip(sorted_indexes, results):
                    call_info = pending_tool_calls[idx]
                    yield "<tool_call>"
                    yield f"<name>{call_info['name']}</name>"
                    yield f"<arguments>{call_info['arguments']}</arguments>"
                    if tool_result.stream_result:
                        yield f"<results>{tool_result.stream_result}</results>"
                    else:
                        yield f"<results>{tool_result.llm_formatted_result}</results>"
                    yield "</tool_call>"

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
                yield "</completion>"

        # If the stream ends without `finish_reason=stop`
        if not self._completed and content_buffer:
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


class R2RStreamingReasoningAgent(R2RStreamingAgent):
    async def process_llm_response(
        self,
        stream: AsyncGenerator[LLMChatCompletionChunk, None],
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Revised processing for the reasoning agent.
        This version:
          1. Accumulates tool calls in a list (each with a unique internal_id).
          2. When finish_reason == "tool_calls", it records the tool calls in the conversation,
             emits Thought messages, and then executes all calls in parallel.
          3. Most importantly, it then yields a matching tool result block (with the same id)
             for each tool call so that Anthropic sees a proper correspondence.
        """
        pending_calls = (
            []
        )  # list of dicts: each has "internal_id", "original_id", "name", "arguments"
        content_buffer = ""
        function_arguments = ""

        inside_thoughts = False

        async for chunk in stream:
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # --- Update our chain-of-thought status based on <Thought> tags ---
            if delta.content:
                num_open = delta.content.count("<Thought>")
                num_close = delta.content.count("</Thought>")
                if num_open > num_close:
                    inside_thoughts = True
                elif inside_thoughts and num_close >= num_open:
                    inside_thoughts = False

            # --- 1. Process any incoming tool_calls ---
            if delta.tool_calls:
                if (
                    "anthropic" in self.rag_generation_config.model
                    or "claude" in self.rag_generation_config.model
                ):
                    for tc in delta.tool_calls:
                        original_id = tc.id if tc.id else None
                        # Check if an existing pending call with this original_id is incomplete.
                        found = None
                        for call in pending_calls:
                            if call["original_id"] == original_id:
                                # If the accumulated arguments do not appear complete (e.g. not ending with "}")
                                if not call["arguments"].strip().endswith("}"):
                                    found = call
                                    break
                        if found is not None:
                            if tc.function.name:
                                found["name"] = tc.function.name
                            if tc.function.arguments:
                                found["arguments"] += tc.function.arguments
                        else:
                            # Create a new call entry. If the original_id is reused,
                            # add a suffix so that each call gets a unique internal_id.
                            new_internal_id = (
                                original_id
                                if original_id
                                else f"call_{len(pending_calls)}"
                            )
                            if original_id is not None:
                                count = sum(
                                    1
                                    for call in pending_calls
                                    if call["original_id"] == original_id
                                )
                                if count > 0:
                                    new_internal_id = f"{original_id}_{count}"
                            pending_calls.append(
                                {
                                    "internal_id": new_internal_id,
                                    "original_id": original_id,
                                    "name": tc.function.name or "",
                                    "arguments": tc.function.arguments or "",
                                }
                            )
                else:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if len(pending_calls) <= idx:
                            pending_calls.append(
                                {
                                    "internal_id": tc.id,  # could be None
                                    "name": tc.function.name or "",
                                    "arguments": tc.function.arguments or "",
                                }
                            )
                        else:
                            # Accumulate partial tool call details
                            if tc.function.arguments:
                                pending_calls[idx][
                                    "arguments"
                                ] += tc.function.arguments

            # --- 2. Process a function_call (if any) ---
            if delta.function_call:
                if delta.function_call.name:
                    function_name = delta.function_call.name
                if delta.function_call.arguments:
                    function_arguments += delta.function_call.arguments

            # --- 3. Process normal content tokens ---
            elif delta.content:
                content_buffer += delta.content
                yield delta.content

            # --- 4. Finalize on finish_reason == "tool_calls" ---
            if finish_reason == "tool_calls":
                # Build a list of tool call descriptors for the conversation message.
                calls_list = []
                for call in pending_calls:
                    calls_list.append(
                        {
                            "id": call["internal_id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": call["arguments"],
                            },
                        }
                    )
                assistant_msg = Message(
                    role="assistant",
                    content=content_buffer or None,
                    tool_calls=calls_list,
                )
                await self.conversation.add_message(assistant_msg)

                # Optionally emit a Thought message for each tool call.
                for call in pending_calls:
                    if inside_thoughts:
                        yield "</Thought>"
                    yield "<Thought>"
                    yield f"\n\nCalling function: {call['name']}, with payload {call['arguments']}"
                    yield "</Thought>"
                    if inside_thoughts:
                        yield "<Thought>"

                # Execute all tool calls in parallel.
                async_calls = [
                    self.handle_function_or_tool_call(
                        call["name"],
                        call["arguments"],
                        tool_id=call["internal_id"],
                        *args,
                        **kwargs,
                    )
                    for call in pending_calls
                ]
                await asyncio.gather(*async_calls)
                # Reset state after processing.
                pending_calls = []
                content_buffer = ""

            # --- 5. Finalize on finish_reason == "stop" ---
            elif finish_reason == "stop":
                if content_buffer:
                    await self.conversation.add_message(
                        Message(role="assistant", content=content_buffer)
                    )
                elif pending_calls:
                    # In case there are pending calls not triggered by a tool_calls finish.
                    calls_list = []
                    for call in pending_calls:
                        calls_list.append(
                            {
                                "id": call["internal_id"],
                                "type": "function",
                                "function": {
                                    "name": call["name"],
                                    "arguments": call["arguments"],
                                },
                            }
                        )
                    assistant_msg = Message(
                        role="assistant",
                        content=content_buffer or None,
                        tool_calls=calls_list,
                    )
                    await self.conversation.add_message(assistant_msg)
                self._completed = True
                return

        # --- Finalize if stream ends unexpectedly ---
        if not self._completed and content_buffer:
            await self.conversation.add_message(
                Message(role="assistant", content=content_buffer)
            )
            self._completed = True

        if not self._completed and pending_calls:
            calls_list = []
            for call in pending_calls:
                calls_list.append(
                    {
                        "id": call["internal_id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": call["arguments"],
                        },
                    }
                )
            assistant_msg = Message(
                role="assistant",
                content=content_buffer or None,
                tool_calls=calls_list,
            )
            await self.conversation.add_message(assistant_msg)
            self._completed = True
