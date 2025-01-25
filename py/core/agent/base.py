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
        function_name = None
        function_arguments = ""
        tool_calls_active = False

        async for chunk in stream:
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # 1) Handle interleaved tool_calls
            if delta.tool_calls:
                tool_calls_active = True
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

            elif finish_reason == "function_call":
                # Single function call handling
                if not function_name:
                    logger.warning("Function name not found in function call.")
                    continue

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

                await self.conversation.add_message(
                    Message(
                        role="function",
                        name=function_name,
                        content=tool_result.llm_formatted_result,
                    )
                )
                function_name, function_arguments, content_buffer = (
                    None,
                    "",
                    "",
                )

            elif finish_reason == "stop":
                # Finalize content if streaming stops
                if content_buffer:
                    await self.conversation.add_message(
                        Message(role="assistant", content=content_buffer)
                    )
                self._completed = True
                yield "</completion>"

        # If the stream ends without `finish_reason=stop`
        if not self._completed and content_buffer:
            await self.conversation.add_message(
                Message(role="assistant", content=content_buffer)
            )
            self._completed = True
            yield "</completion>"

        # async def process_llm_response(
        #     self,
        #     stream: AsyncGenerator[LLMChatCompletionChunk, None],
        #     *args,
        #     **kwargs,
        # ) -> AsyncGenerator[str, None]:
        #     """
        #     Modified to:
        #      1) Collect partial tool calls in a dict keyed by their .index
        #      2) Execute them in parallel (asyncio.gather) once finish_reason="tool_calls"
        #     """
        #     # Dictionary:
        #     #   pending_tool_calls[index] = {
        #     #       "id": str or None,
        #     #       "name": str,
        #     #       "arguments": str,
        #     #   }
        #     pending_tool_calls = {}

        #     # For single function_call logic
        #     function_name = None
        #     function_arguments = ""

        #     # Buffer for normal text
        #     content_buffer = ""

        #     async for chunk in stream:
        #         delta = chunk.choices[0].delta
        #         print(f'chunk={chunk}, delta = {delta}')
        #         # 1) Handle partial tool_calls
        #         if delta.tool_calls:
        #             for tc in delta.tool_calls:
        #                 idx = tc.index
        #                 if idx not in pending_tool_calls:
        #                     pending_tool_calls[idx] = {
        #                         "id": tc.id,  # might be None
        #                         "name": tc.function.name or "",
        #                         "arguments": tc.function.arguments or "",
        #                     }
        #                 else:
        #                     # Accumulate partial arguments
        #                     if tc.function.name:
        #                         pending_tool_calls[idx]["name"] = tc.function.name
        #                     if tc.function.arguments:
        #                         pending_tool_calls[idx][
        #                             "arguments"
        #                         ] += tc.function.arguments
        #                     # If we see an ID on a later chunk, set it now
        #                     if tc.id and not pending_tool_calls[idx]["id"]:
        #                         pending_tool_calls[idx]["id"] = tc.id

        #         # 2) Handle partial function_call
        #         if delta.function_call:
        #             if delta.function_call.name:
        #                 function_name = delta.function_call.name
        #             if delta.function_call.arguments:
        #                 function_arguments += delta.function_call.arguments

        #         # 3) Handle normal text
        #         elif delta.content:
        #             if content_buffer == "":
        #                 yield "<completion>"
        #             content_buffer += delta.content
        #             yield delta.content

        #         # 4) Check finish_reason
        #         finish_reason = chunk.choices[0].finish_reason

        #         if finish_reason == "tool_calls":
        #             # The model has finished specifying this entire set of tool calls in an assistant message.
        #             if not pending_tool_calls:
        #                 logger.warning(
        #                     "Got finish_reason=tool_calls but no pending tool calls."
        #                 )
        #             else:
        #                 # 4a) Build a single 'assistant' message with all tool_calls
        #                 calls_list = []
        #                 # Sort by index to ensure consistent ordering
        #                 sorted_indexes = sorted(pending_tool_calls.keys())
        #                 for idx in sorted_indexes:
        #                     call_info = pending_tool_calls[idx]
        #                     call_id = (
        #                         call_info["id"]
        #                         if call_info["id"]
        #                         else f"call_{idx}"
        #                     )
        #                     calls_list.append(
        #                         {
        #                             "id": call_id,
        #                             "type": "function",
        #                             "function": {
        #                                 "name": call_info["name"],
        #                                 "arguments": call_info["arguments"],
        #                             },
        #                         }
        #                     )

        #                 assistant_msg = Message(
        #                     role="assistant",
        #                     content=content_buffer or None,
        #                     tool_calls=calls_list,
        #                 )
        #                 await self.conversation.add_message(assistant_msg)

        #                 # 4b) Execute them in parallel using asyncio.gather
        #                 async_calls = []
        #                 for idx in sorted_indexes:
        #                     call_info = pending_tool_calls[idx]
        #                     call_id = call_info["id"] or f"call_{idx}"
        #                     async_calls.append(
        #                         self.handle_function_or_tool_call(
        #                             call_info["name"],
        #                             call_info["arguments"],
        #                             tool_id=call_id,
        #                             *args,
        #                             **kwargs,
        #                         )
        #                     )
        #                 results = await asyncio.gather(*async_calls)

        #                 # 4c) Now yield the <tool_call> blocks in the same order
        #                 for idx, tool_result in zip(sorted_indexes, results):
        #                     # We re-lookup the name, arguments, id
        #                     call_info = pending_tool_calls[idx]
        #                     call_id = call_info["id"] or f"call_{idx}"
        #                     call_name = call_info["name"]
        #                     call_args = call_info["arguments"]

        #                     yield "<tool_call>"
        #                     yield f"<name>{call_name}</name>"
        #                     yield f"<arguments>{call_args}</arguments>"

        #                     if tool_result.stream_result:
        #                         yield f"<results>{tool_result.stream_result}</results>"
        #                     else:
        #                         yield f"<results>{tool_result.llm_formatted_result}</results>"

        #                     yield "</tool_call>"

        #                 # 4e) Reset
        #                 pending_tool_calls.clear()
        #                 content_buffer = ""

        #         elif finish_reason == "function_call":
        #             # Single function call approach
        #             if not function_name:
        #                 logger.info("Function name not found in function call.")
        #                 continue

        #             # Add the assistant message with function_call
        #             assistant_msg = Message(
        #                 role="assistant",
        #                 content=content_buffer if content_buffer else None,
        #                 function_call={
        #                     "name": function_name,
        #                     "arguments": function_arguments,
        #                 },
        #             )
        #             await self.conversation.add_message(assistant_msg)

        #             yield "<function_call>"
        #             yield f"<name>{function_name}</name>"
        #             yield f"<arguments>{function_arguments}</arguments>"

        #             tool_result = await self.handle_function_or_tool_call(
        #                 function_name, function_arguments, *args, **kwargs
        #             )
        #             if tool_result.stream_result:
        #                 yield f"<results>{tool_result.stream_result}</results>"
        #             else:
        #                 yield f"<results>{tool_result.llm_formatted_result}</results>"

        #             yield "</function_call>"

        #             # Add a function-role message
        #             await self.conversation.add_message(
        #                 Message(
        #                     role="function",
        #                     name=function_name,
        #                     content=tool_result.llm_formatted_result,
        #                 )
        #             )

        #             function_name = None
        #             function_arguments = ""
        #             content_buffer = ""

        #         elif finish_reason == "stop":
        #             # The model is done producing text
        #             if content_buffer:
        #                 await self.conversation.add_message(
        #                     Message(role="assistant", content=content_buffer)
        #                 )
        #             self._completed = True
        #             yield "</completion>"

        # After the stream ends
        if content_buffer and not self._completed:
            await self.conversation.add_message(
                Message(role="assistant", content=content_buffer)
            )
            self._completed = True
            yield "</completion>"


# import asyncio
# import logging
# from abc import ABCMeta
# from typing import AsyncGenerator, Generator, Optional

# from core.base.abstractions import (
#     AsyncSyncMeta,
#     LLMChatCompletion,
#     LLMChatCompletionChunk,
#     Message,
#     syncable,
# )
# from core.base.agent import Agent, Conversation

# logger = logging.getLogger()


# class CombinedMeta(AsyncSyncMeta, ABCMeta):
#     pass


# def sync_wrapper(async_gen):
#     loop = asyncio.get_event_loop()

#     def wrapper():
#         try:
#             while True:
#                 try:
#                     yield loop.run_until_complete(async_gen.__anext__())
#                 except StopAsyncIteration:
#                     break
#         finally:
#             loop.run_until_complete(async_gen.aclose())

#     return wrapper()


# class R2RAgent(Agent, metaclass=CombinedMeta):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._reset()

#     def _reset(self):
#         self._completed = False
#         self.conversation = Conversation()

#     @syncable
#     async def arun(
#         self,
#         messages: list[Message],
#         system_instruction: Optional[str] = None,
#         *args,
#         **kwargs,
#     ) -> list[dict]:
#         # (Same as before)
#         self._reset()
#         await self._setup(system_instruction)

#         if messages:
#             for message in messages:
#                 await self.conversation.add_message(message)

#         while not self._completed:
#             messages_list = await self.conversation.get_messages()
#             generation_config = self.get_generation_config(messages_list[-1])
#             response = await self.llm_provider.aget_completion(
#                 messages_list,
#                 generation_config,
#             )
#             await self.process_llm_response(response, *args, **kwargs)

#         # Return final content
#         all_messages: list[dict] = await self.conversation.get_messages()
#         all_messages.reverse()

#         output_messages = []
#         for message_2 in all_messages:
#             if (
#                 message_2.get("content")
#                 and message_2.get("content") != messages[-1].content
#             ):
#                 output_messages.append(message_2)
#             else:
#                 break
#         output_messages.reverse()

#         return output_messages

#     async def process_llm_response(
#         self, response: LLMChatCompletion, *args, **kwargs
#     ) -> None:
#         # (Unchanged from your original snippet)
#         if not self._completed:
#             message = response.choices[0].message
#             if message.function_call:
#                 await self.handle_function_or_tool_call(
#                     message.function_call.name,
#                     message.function_call.arguments,
#                     *args,
#                     **kwargs,
#                 )
#             elif message.tool_calls:
#                 for tool_call in message.tool_calls:
#                     await self.handle_function_or_tool_call(
#                         tool_call.function.name,
#                         tool_call.function.arguments,
#                         *args,
#                         **kwargs,
#                     )
#             else:
#                 await self.conversation.add_message(
#                     Message(role="assistant", content=message.content)
#                 )
#                 self._completed = True


# class R2RStreamingAgent(R2RAgent):
#     async def arun(  # type: ignore
#         self,
#         system_instruction: Optional[str] = None,
#         messages: Optional[list[Message]] = None,
#         *args,
#         **kwargs,
#     ) -> AsyncGenerator[str, None]:
#         self._reset()
#         await self._setup(system_instruction)

#         if messages:
#             for message in messages:
#                 await self.conversation.add_message(message)

#         while not self._completed:
#             messages_list = await self.conversation.get_messages()
#             generation_config = self.get_generation_config(
#                 messages_list[-1], stream=True
#             )
#             stream = self.llm_provider.aget_completion_stream(
#                 messages_list,
#                 generation_config,
#             )
#             async for proc_chunk in self.process_llm_response(
#                 stream, *args, **kwargs
#             ):
#                 yield proc_chunk

#     def run(
#         self, system_instruction, messages, *args, **kwargs
#     ) -> Generator[str, None, None]:
#         return sync_wrapper(
#             self.arun(system_instruction, messages, *args, **kwargs)
#         )

#     async def process_llm_response(
#         self,
#         stream: AsyncGenerator[LLMChatCompletionChunk, None],
#         *args,
#         **kwargs,
#     ) -> AsyncGenerator[str, None]:
#         """
#         Revised to handle partial or multiple tool calls where 'id' can be None
#         in early chunks. We'll map by 'index' first, then rename or unify if
#         we eventually see an 'id'.
#         """
#         # pending_tool_calls will map either index or final call_id -> {
#         #    "index": int,
#         #    "id": str or None,
#         #    "name": str,
#         #    "arguments": str
#         # }
#         pending_tool_calls = {}

#         # For single function_call logic
#         function_name = None
#         function_arguments = ""

#         # Buffer for normal text
#         content_buffer = ""

#         async for chunk in stream:
#             print('chunjk = ', chunk)
#             delta = chunk.choices[0].delta

#             #
#             # 1) Handle partial tool_calls
#             #
#             if delta.tool_calls:
#                 # Possibly multiple calls at once
#                 for tool_call in delta.tool_calls:
#                     index = tool_call.index
#                     call_id = tool_call.id  # May be None in early partial chunks
#                     func_name = tool_call.function.name
#                     func_args = tool_call.function.arguments

#                     # 1a) If we already have an entry for this index, retrieve it
#                     if index in pending_tool_calls:
#                         entry = pending_tool_calls[index]
#                     else:
#                         # Otherwise, create a new entry
#                         entry = {
#                             "index": index,
#                             "id": None,
#                             "name": "",
#                             "arguments": ""
#                         }
#                         pending_tool_calls[index] = entry

#                     # 1b) Merge in name/arguments
#                     if func_name:  # if not empty
#                         entry["name"] = func_name
#                     if func_args:
#                         entry["arguments"] += func_args

#                     # 1c) If we suddenly see an 'id', we rename/unify the dictionary key
#                     if call_id and not entry["id"]:
#                         # We haven't set an ID yet, so adopt call_id
#                         entry["id"] = call_id
#                         # Also copy this entry so we can look it up by that ID too
#                         pending_tool_calls[call_id] = entry
#                     elif call_id and entry["id"] and entry["id"] != call_id:
#                         # This means we previously had a different ID, theoretically unusual.
#                         # For safety, unify or pick the newest.
#                         old_id = entry["id"]
#                         # We might delete the old key to avoid confusion
#                         if old_id in pending_tool_calls and old_id != index:
#                             del pending_tool_calls[old_id]
#                         # Now set the new ID
#                         entry["id"] = call_id
#                         pending_tool_calls[call_id] = entry

#             #
#             # 2) Handle partial function_call
#             #
#             if delta.function_call:
#                 if delta.function_call.name:
#                     function_name = delta.function_call.name
#                 if delta.function_call.arguments:
#                     function_arguments += delta.function_call.arguments

#             #
#             # 3) Handle normal text
#             #
#             elif delta.content:
#                 if content_buffer == "":
#                     yield "<completion>"
#                 content_buffer += delta.content
#                 yield delta.content

#             #
#             # 4) Check finish_reason
#             #
#             finish_reason = chunk.choices[0].finish_reason

#             if finish_reason == "tool_calls":
#                 # The entire assistant message with these calls is done
#                 # So let's gather them up properly, add an assistant message with tool_calls,
#                 # and yield results. Also add function-role messages for each call’s result.
#                 if not pending_tool_calls:
#                     logger.warning("Got finish_reason=tool_calls but no pending calls.")
#                 else:
#                     # Build the tool_calls list for the assistant message
#                     calls_list = []
#                     # We'll figure out which entries in pending_tool_calls are "real" calls
#                     # i.e. those keyed by an 'index' we haven't processed yet
#                     # We only process each call *once*
#                     processed_indices = []

#                     for key, data in list(pending_tool_calls.items()):
#                         # If key is an integer index or if data["index"] is not None,
#                         # that means this is the "primary" record.
#                         # If key is a string id, it's the same record, just another pointer.
#                         if isinstance(key, int):
#                             # This is the primary record for that tool call
#                             processed_indices.append(key)
#                             # Now figure out the final id
#                             call_id = data["id"] or f"call_{data['index']}"
#                             calls_list.append(
#                                 {
#                                     "id": call_id,
#                                     "type": "function",
#                                     "function": {
#                                         "name": data["name"],
#                                         "arguments": data["arguments"]
#                                     }
#                                 }
#                             )

#                     # Now we have calls_list for the entire assistant message
#                     assistant_msg = Message(
#                         role="assistant",
#                         content=content_buffer if content_buffer else None,
#                         tool_calls=calls_list,
#                     )
#                     await self.conversation.add_message(assistant_msg)

#                     # Next, yield the <tool_call> blocks and do handle_function_or_tool_call
#                     for call in calls_list:
#                         call_id = call["id"]
#                         call_name = call["function"]["name"]
#                         call_args = call["function"]["arguments"]

#                         yield "<tool_call>"
#                         yield f"<name>{call_name}</name>"
#                         yield f"<arguments>{call_args}</arguments>"

#                         tool_result = await self.handle_function_or_tool_call(
#                             call_name, call_args, tool_id=call_id, *args, **kwargs
#                         )
#                         print('conversation = ', self.conversation.messages)
#                         if tool_result.stream_result:
#                             yield f"<results>{tool_result.stream_result}</results>"
#                         else:
#                             yield f"<results>{tool_result.llm_formatted_result}</results>"

#                         yield "</tool_call>"

#                         # And add the function-role message
#                         await self.conversation.add_message(
#                             Message(
#                                 role="function",
#                                 name=call_id,
#                                 content=tool_result.llm_formatted_result,
#                             )
#                         )

#                     # Finally, remove processed calls from pending_tool_calls
#                     for idx in processed_indices:
#                         data = pending_tool_calls.pop(idx, None)
#                         if data and data["id"]:
#                             pending_tool_calls.pop(data["id"], None)

#                     # Reset content
#                     content_buffer = ""

#             elif finish_reason == "function_call":
#                 # Single function call approach
#                 if not function_name:
#                     logger.info("Function name not found in function call.")
#                     continue

#                 # Add the assistant message with function_call
#                 assistant_msg = Message(
#                     role="assistant",
#                     content=content_buffer if content_buffer else None,
#                     function_call={
#                         "name": function_name,
#                         "arguments": function_arguments,
#                     },
#                 )
#                 await self.conversation.add_message(assistant_msg)

#                 # yield the original logic
#                 yield "<function_call>"
#                 yield f"<name>{function_name}</name>"
#                 yield f"<arguments>{function_arguments}</arguments>"

#                 tool_result = await self.handle_function_or_tool_call(
#                     function_name, function_arguments, *args, **kwargs
#                 )
#                 if tool_result.stream_result:
#                     yield f"<results>{tool_result.stream_result}</results>"
#                 else:
#                     yield f"<results>{tool_result.llm_formatted_result}</results>"

#                 yield "</function_call>"

#                 # Add function-role message
#                 await self.conversation.add_message(
#                     Message(
#                         role="function",
#                         name=function_name,
#                         content=tool_result.llm_formatted_result,
#                     )
#                 )

#                 function_name = None
#                 function_arguments = ""
#                 content_buffer = ""

#             elif finish_reason == "stop":
#                 # We're done: add leftover content as normal assistant message
#                 if content_buffer:
#                     await self.conversation.add_message(
#                         Message(role="assistant", content=content_buffer)
#                     )
#                 self._completed = True
#                 yield "</completion>"

#         # End of the stream
#         if content_buffer and not self._completed:
#             await self.conversation.add_message(
#                 Message(role="assistant", content=content_buffer)
#             )
#             self._completed = True
#             yield "</completion>"
