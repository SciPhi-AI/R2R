import asyncio
import logging
import re
from abc import ABCMeta
from typing import AsyncGenerator, Generator, Optional

from core.base import (
    AsyncSyncMeta,
    LLMChatCompletion,
    LLMChatCompletionChunk,
    Message,
    ToolCallData,
    ToolCallEvent,
    ToolResultData,
    ToolResultEvent,
    syncable,
)
from core.utils import yield_sse_event
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
    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Return an async generator that yields SSE lines with:
          - partial text
          - tool calls
          - tool results
          - final answer
        No citation detection or rewriting in this version.
        """
        self._reset()
        await self._setup(system_instruction)

        if messages:
            for msg in messages:
                await self.conversation.add_message(msg)

        async def sse_generator() -> AsyncGenerator[str, None]:
            partial_text_buffer = ""
            pending_tool_calls = {}

            while not self._completed:
                msgs_list = await self.conversation.get_messages()
                generation_config = self.get_generation_config(
                    msgs_list[-1], stream=True
                )
                llm_stream = self.llm_provider.aget_completion_stream(
                    msgs_list, generation_config
                )

                async for chunk in llm_stream:
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason

                    # 1) Accumulate normal partial text
                    if delta.content:
                        partial_text_buffer += delta.content

                        # Emit SSE "message" event with newly arrived text
                        new_substring_start = len(partial_text_buffer) - len(
                            delta.content
                        )
                        new_text_to_emit = partial_text_buffer[
                            new_substring_start:
                        ]

                        message_evt_payload = {
                            "id": "msg_partial",
                            "object": "agent.message.delta",
                            "delta": {
                                "content": [
                                    {
                                        "type": "text",
                                        "payload": {
                                            "value": new_text_to_emit,
                                            "annotations": [],
                                        },
                                    }
                                ]
                            },
                        }
                        async for line in yield_sse_event(
                            "message", message_evt_payload
                        ):
                            yield line

                    # 2) If partial tool_calls
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in pending_tool_calls:
                                pending_tool_calls[idx] = {
                                    "id": tc.id,
                                    "name": tc.function.name or "",
                                    "arguments": tc.function.arguments or "",
                                }
                            else:
                                if tc.function.name:
                                    pending_tool_calls[idx][
                                        "name"
                                    ] = tc.function.name
                                if tc.function.arguments:
                                    pending_tool_calls[idx][
                                        "arguments"
                                    ] += tc.function.arguments

                    # 3) If partial function_call
                    if delta.function_call:
                        # (Optionally handle single partial function call if needed)
                        pass

                    # 4) On finish_reason="tool_calls", do the tool calls
                    if finish_reason == "tool_calls":
                        # Freeze partial content so far
                        calls_list = []
                        sorted_indexes = sorted(pending_tool_calls.keys())
                        for idx in sorted_indexes:
                            call_info = pending_tool_calls[idx]
                            tool_call_id = call_info["id"] or f"call_{idx}"
                            calls_list.append(
                                {
                                    "tool_call_id": tool_call_id,
                                    "name": call_info["name"],
                                    "arguments": call_info["arguments"],
                                }
                            )

                        # SSE "tool_call" events
                        for cinfo in calls_list:
                            tc_data = ToolCallData(**cinfo)
                            tc_event = ToolCallEvent(
                                event="tool_call", data=tc_data
                            )
                            async for line in yield_sse_event(
                                "tool_call", tc_event.dict()["data"]
                            ):
                                yield line

                        # Store an assistant message capturing these calls
                        assistant_msg = Message(
                            role="assistant",
                            content=partial_text_buffer or None,
                            tool_calls=[
                                {
                                    "id": call["tool_call_id"],
                                    "type": "function",
                                    "function": {
                                        "name": call["name"],
                                        "arguments": call["arguments"],
                                    },
                                }
                                for call in calls_list
                            ],
                        )
                        await self.conversation.add_message(assistant_msg)

                        # 5) Execute each call
                        tool_results = await asyncio.gather(
                            *[
                                self.handle_function_or_tool_call(
                                    call["name"],
                                    call["arguments"],
                                    tool_id=call["tool_call_id"],
                                )
                                for call in calls_list
                            ]
                        )

                        # SSE "tool_result" for each
                        for call, result_obj in zip(calls_list, tool_results):
                            output_text = (
                                result_obj.stream_result
                                or result_obj.llm_formatted_result
                                or ""
                            )
                            result_data = ToolResultData(
                                tool_call_id=call["tool_call_id"],
                                role="tool",
                                content=output_text,
                            )
                            result_evt = ToolResultEvent(
                                event="tool_result", data=result_data
                            )
                            async for line in yield_sse_event(
                                "tool_result", result_evt.dict()["data"]
                            ):
                                yield line

                        # Clear partial text & pending calls
                        pending_tool_calls.clear()
                        partial_text_buffer = ""

                    elif finish_reason == "stop":
                        # Final step: store leftover text as a message
                        if pending_tool_calls:
                            # If leftover calls exist, you could handle them similarly
                            pass
                        elif partial_text_buffer:
                            await self.conversation.add_message(
                                Message(
                                    role="assistant",
                                    content=partial_text_buffer,
                                )
                            )

                        # SSE final_answer
                        final_ans_evt = {
                            "id": "msg_final",
                            "object": "agent.final_answer",
                            "generated_answer": partial_text_buffer,
                        }
                        async for line in yield_sse_event(
                            "final_answer", final_ans_evt
                        ):
                            yield line

                        # SSE done
                        yield "event: done\n"
                        yield "data: [DONE]\n\n"

                        self._completed = True
                        break

            # If we ever exit the loop without finishing:
            if not self._completed:
                yield "event: done\n"
                yield "data: [DONE]\n\n"
                self._completed = True

        async for line in sse_generator():
            yield line


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
        if "anthropic" in self.rag_generation_config.model:
            pending_tool_calls = {}
            content_buffer = ""
            function_arguments = ""

            inside_thoughts = False
            async for chunk in stream:
                delta = chunk.choices[0].delta

                if delta.content and delta.content.count(
                    "<Thought>"
                ) > delta.content.count("</Thought>"):
                    inside_thoughts = True
                elif (
                    delta.content
                    and inside_thoughts
                    and delta.content.count("</Thought>")
                    > delta.content.count("<Thought>")
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
                                pending_tool_calls[idx][
                                    "name"
                                ] = tc.function.name
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
                            yield "</Thought>"
                        yield "<Thought>"
                        yield f"Calling function: {tool_call['name']}, with payload `{tool_call['arguments']}..."
                        yield "</Thought>"
                        if inside_thoughts:
                            yield "<Thought>"
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
                    if pending_tool_calls:
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

                        # Clear the tool call state
                        pending_tool_calls.clear()

                        continue

                    elif content_buffer:
                        await self.conversation.add_message(
                            Message(role="assistant", content=content_buffer)
                        )

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
        else:
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
                                    if (
                                        not call["arguments"]
                                        .strip()
                                        .endswith("}")
                                    ):
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
                                        new_internal_id = (
                                            f"{original_id}_{count}"
                                        )
                                pending_calls.append(
                                    {
                                        "internal_id": new_internal_id,
                                        "original_id": original_id,
                                        "name": tc.function.name or "",
                                        "arguments": tc.function.arguments
                                        or "",
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
                                        "arguments": tc.function.arguments
                                        or "",
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
                    if pending_calls:
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

                        # Clear the tool call state
                        pending_tool_calls.clear()
                        continue

                    elif content_buffer:
                        await self.conversation.add_message(
                            Message(role="assistant", content=content_buffer)
                        )

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
