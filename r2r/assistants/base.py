import asyncio
import json
from abc import ABCMeta
from typing import AsyncGenerator, Generator, Optional

from r2r.base import (
    Assistant,
    AsyncSyncMeta,
    LLMChatCompletion,
    LLMChatCompletionChunk,
    Message,
    ToolResult,
    syncable,
)


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


class R2RAssistant(Assistant, metaclass=CombinedMeta):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._reset()

    def _reset(self):
        self._completed = False
        self.conversation = []

    @syncable
    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> list[LLMChatCompletion]:
        self._reset()

        if system_instruction or not self.conversation:
            self._setup(system_instruction)

        if messages:
            self.conversation.extend(messages)

        while not self._completed:
            generation_config = self.get_generation_config(
                self.conversation[-1]
            )
            response = await self.llm_provider.aget_completion(
                [
                    ele.model_dump(exclude_none=True)
                    for ele in self.conversation
                ],
                generation_config,
            )
            await self.process_llm_response(response, *args, **kwargs)

        return self.conversation

    async def process_llm_response(
        self, response: LLMChatCompletion, *args, **kwargs
    ) -> str:
        if not self._completed:
            message = response.choices[0].message
            if message.function_call:
                await self.handle_tool_call(
                    message.function_call.name,
                    message.function_call.arguments,
                    *args,
                    **kwargs,
                )
            elif message.tool_calls:
                for tool_call in message.tool_calls:
                    await self.handle_tool_call(
                        tool_call.function.name,
                        tool_call.function.arguments,
                        *args,
                        **kwargs,
                    )
            else:
                self.conversation.append(
                    Message(role="assistant", content=message.content)
                )
                self._completed = True


class R2RStreamingAssistant(Assistant):
    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        try:
            if system_instruction or not self.conversation:
                self._setup(system_instruction)

            if messages:
                self.conversation.extend(messages)

            while not self._completed:
                generation_config = self.get_generation_config(
                    self.conversation[-1], stream=True
                )
                stream = self.llm_provider.get_completion_stream(
                    [
                        ele.model_dump(exclude_none=True)
                        for ele in self.conversation
                    ],
                    generation_config,
                )
                async for chunk in self.process_llm_response(
                    stream, *args, **kwargs
                ):
                    yield chunk
        finally:
            self._completed = False
            self.conversation = []

    def run(
        self, system_instruction, messages, *args, **kwargs
    ) -> Generator[str, None, None]:
        return sync_wrapper(
            self.arun(system_instruction, messages, *args, **kwargs)
        )

    async def process_llm_response(
        self, stream: LLMChatCompletionChunk, *args, **kwargs
    ) -> AsyncGenerator[str, None]:
        function_name = None
        function_arguments = ""
        content_buffer = ""

        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    results = await self.handle_tool_call(
                        tool_call.function.name,
                        tool_call.function.arguments,
                        # FIXME: tool_call.id,
                        *args,
                        **kwargs,
                    )

                    yield f"<tool_call>"
                    yield f"<name>{tool_call.function.name}</name>"
                    yield f"<arguments>{tool_call.function.arguments}</arguments>"
                    yield f"<results>{results}</results>"
                    yield f"</tool_call>"

            if delta.function_call:
                if delta.function_call.name:
                    function_name = delta.function_call.name
                if delta.function_call.arguments:
                    function_arguments += delta.function_call.arguments
            elif delta.content:
                content_buffer += delta.content
                yield delta.content

            if chunk.choices[0].finish_reason == "function_call":
                yield "<function_call>"
                yield f"<name>{function_name}</name>"
                yield f"<arguments>{function_arguments}</arguments>"
                tool_result = await self.handle_tool_call(
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
                    self.conversation.append(
                        Message(role="assistant", content=content_buffer)
                    )
                self._completed = True

    async def handle_tool_call(
        self,
        tool_name: str,
        tool_arguments: str,
        tool_id: Optional[str] = None,
        *args,
        **kwargs,
    ) -> ToolResult:
        tool = next(
            (t for t in self.config.tools if t.name == tool_name), None
        )
        if tool:
            raw_result = await tool.results_function(
                *args, **kwargs, **json.loads(tool_arguments)
            )
            print("raw_result = ", raw_result)
            llm_formatted_result = tool.llm_format_function(raw_result)

            tool_result = ToolResult(
                raw_result=raw_result,
                llm_formatted_result=llm_formatted_result,
            )

            if tool.stream_function:
                tool_result.stream_result = tool.stream_function(raw_result)

            self.conversation.append(
                Message(
                    role="function",
                    name=tool.name,
                    content=llm_formatted_result,
                )
            )

            return tool_result
        else:
            raise ValueError(f"Tool {tool_name} not found")


# import asyncio
# from abc import ABCMeta
# from typing import Any, AsyncGenerator, Generator, Optional
# import json
# from r2r.base import (
#     Assistant,
#     AsyncSyncMeta,
#     LLMChatCompletion,
#     LLMChatCompletionChunk,
#     Message,
#     syncable,
#     ToolResult
# )


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


# class R2RAssistant(Assistant, metaclass=CombinedMeta):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._reset()

#     def _reset(self):
#         self._completed = False
#         self.conversation = []

#     @syncable
#     async def arun(
#         self,
#         system_instruction: Optional[str] = None,
#         messages: Optional[list[Message]] = None,
#         *args,
#         **kwargs,
#     ) -> list[LLMChatCompletion]:
#         self._reset()

#         if system_instruction or not self.conversation:
#             self._setup(system_instruction)

#         if messages:
#             self.conversation.extend(messages)

#         while not self._completed:
#             generation_config = self.get_generation_config(
#                 self.conversation[-1]
#             )
#             response = await self.llm_provider.aget_completion(
#                 [
#                     ele.model_dump(exclude_none=True)
#                     for ele in self.conversation
#                 ],
#                 generation_config,
#             )
#             await self.process_llm_response(response, *args, **kwargs)

#         return self.conversation

#     async def process_llm_response(
#         self, response: LLMChatCompletion, *args, **kwargs
#     ) -> str:
#         if not self._completed:
#             message = response.choices[0].message
#             if message.function_call:
#                 await self.handle_tool_call(
#                     message.function_call.name,
#                     message.function_call.arguments,
#                     *args,
#                     **kwargs,
#                 )
#             elif message.tool_calls:
#                 for tool_call in message.tool_calls:
#                     await self.handle_tool_call(
#                         tool_call.function.name,
#                         tool_call.function.arguments,
#                         tool_call.id,
#                         *args,
#                         **kwargs,
#                     )
#             else:
#                 self.conversation.append(
#                     Message(role="assistant", content=message.content)
#                 )
#                 self._completed = True

#     async def handle_tool_call(
#         self, tool_name: str, tool_arguments: str, tool_id: Optional[str] = None, *args, **kwargs
#     ) -> ToolResult:
#         tool = next((t for t in self.config.tools if t.name == tool_name), None)
#         if tool:
#             raw_result = await tool.results_function(*args, **kwargs, **json.loads(tool_arguments))
#             print('raw_result = ', raw_result)
#             llm_formatted_result = tool.llm_format_function(raw_result)

#             tool_result = ToolResult(
#                 raw_result=raw_result,
#                 llm_formatted_result=llm_formatted_result
#             )

#             if tool.stream_function:
#                 tool_result.stream_result = tool.stream_function(raw_result)

#             self.conversation.append(
#                 Message(role="function", name=tool.name, content=llm_formatted_result)
#             )

#             return tool_result
#         else:
#             raise ValueError(f"Tool {tool_name} not found")


# class R2RStreamingAssistant(Assistant, metaclass=CombinedMeta):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._reset()

#     def _reset(self):
#         self._completed = False
#         self.conversation = []

#     @syncable
#     async def arun(
#         self,
#         system_instruction: Optional[str] = None,
#         messages: Optional[list[Message]] = None,
#         *args,
#         **kwargs,
#     ) -> AsyncGenerator[str, None]:
#         try:
#             if system_instruction or not self.conversation:
#                 self._setup(system_instruction)

#             if messages:
#                 self.conversation.extend(messages)

#             while not self._completed:
#                 generation_config = self.get_generation_config(
#                     self.conversation[-1], stream=True
#                 )
#                 stream = self.llm_provider.get_completion_stream(
#                     [
#                         ele.model_dump(exclude_none=True)
#                         for ele in self.conversation
#                     ],
#                     generation_config,
#                 )
#                 async for chunk in self.process_llm_response(
#                     stream, *args, **kwargs
#                 ):
#                     yield chunk
#         finally:
#             self._completed = False
#             self.conversation = []

#     def run(
#         self, system_instruction, messages, *args, **kwargs
#     ) -> Generator[str, None, None]:
#         return sync_wrapper(
#             self.arun(system_instruction, messages, *args, **kwargs)
#         )

#     async def process_llm_response(
#         self, stream: LLMChatCompletionChunk, *args, **kwargs
#     ) -> AsyncGenerator[str, None]:
#         function_name = None
#         function_arguments = ""
#         content_buffer = ""

#         for chunk in stream:
#             delta = chunk.choices[0].delta
#             if delta.tool_calls:
#                 for tool_call in delta.tool_calls:
#                     yield f"<tool_call>"
#                     yield f"<name>{tool_call.function.name}</name>"
#                     yield f"<arguments>{tool_call.function.arguments}</arguments>"
#                     tool_result = await self.handle_tool_call(
#                         tool_call.function.name,
#                         tool_call.function.arguments,
#                         tool_call.id,
#                         *args,
#                         **kwargs,
#                     )
#                     if tool_result.stream_result:
#                         yield f"<results>{tool_result.stream_result}</results>"
#                     else:
#                         yield f"<results>{tool_result.llm_formatted_result}</results>"
#                     yield f"</tool_call>"

#             if delta.function_call:
#                 if delta.function_call.name:
#                     function_name = delta.function_call.name
#                 if delta.function_call.arguments:
#                     function_arguments += delta.function_call.arguments
#             elif delta.content:
#                 content_buffer += delta.content
#                 yield delta.content

#             if chunk.choices[0].finish_reason == "function_call":
#                 yield "<function_call>"
#                 yield f"<name>{function_name}</name>"
#                 yield f"<arguments>{function_arguments}</arguments>"
#                 tool_result = await self.handle_tool_call(
#                     function_name, function_arguments, None, *args, **kwargs
#                 )
#                 if tool_result.stream_result:
#                     yield f"<results>{tool_result.stream_result}</results>"
#                 else:
#                     yield f"<results>{tool_result.llm_formatted_result}</results>"
#                 yield "</function_call>"

#                 function_name = None
#                 function_arguments = ""

#                 self.arun(*args, **kwargs)

#             elif chunk.choices[0].finish_reason == "stop":
#                 if content_buffer:
#                     self.conversation.append(
#                         Message(role="assistant", content=content_buffer)
#                     )
#                 self._completed = True

#     async def handle_tool_call(
#         self, tool_name: str, tool_arguments: str, tool_id: Optional[str] = None, *args, **kwargs
#     ) -> ToolResult:
#         tool = next((t for t in self.config.tools if t.name == tool_name), None)
#         if tool:
#             raw_result = await tool.results_function(*args, **kwargs, **json.loads(tool_arguments))
#             llm_formatted_result = tool.llm_format_function(raw_result)

#             tool_result = ToolResult(
#                 raw_result=raw_result,
#                 llm_formatted_result=llm_formatted_result
#             )

#             if tool.stream_function:
#                 tool_result.stream_result = tool.stream_function(raw_result)

#             self.conversation.append(
#                 Message(role="function", name=tool.name, content=llm_formatted_result)
#             )

#             return tool_result
#         else:
#             raise ValueError(f"Tool {tool_name} not found")


# # class R2RAssistant(Assistant, metaclass=CombinedMeta):
# #     def __init__(self, *args, **kwargs):
# #         super().__init__(*args, **kwargs)
# #         self._reset()

# #     def _reset(self):
# #         self._completed = False
# #         self.conversation = []

# #     @syncable
# #     async def arun(
# #         self,
# #         system_instruction: Optional[str] = None,
# #         messages: Optional[list[Message]] = None,
# #         *args,
# #         **kwargs,
# #     ) -> list[LLMChatCompletion]:
# #         self._reset()

# #         if system_instruction or not self.conversation:
# #             self._setup(system_instruction)

# #         if messages:
# #             self.conversation.extend(messages)

# #         while not self._completed:
# #             generation_config = self.get_generation_config(
# #                 self.conversation[-1]
# #             )
# #             response = await self.llm_provider.aget_completion(
# #                 [
# #                     ele.model_dump(exclude_none=True)
# #                     for ele in self.conversation
# #                 ],
# #                 generation_config,
# #             )
# #             await self.process_llm_response(response, *args, **kwargs)

# #         return self.conversation

# #     async def process_llm_response(
# #         self, response: LLMChatCompletion, *args, **kwargs
# #     ) -> str:
# #         if not self._completed:
# #             message = response.choices[0].message
# #             if message.function_call:
# #                 await self.handle_tool_call(
# #                     message.function_call.name,
# #                     message.function_call.arguments,
# #                     *args,
# #                     **kwargs,
# #                 )
# #             elif message.tool_calls:
# #                 for tool_call in message.tool_calls:
# #                     await self.handle_tool_call(
# #                         tool_call.function.name,
# #                         tool_call.function.arguments,
# #                         tool_call.id,
# #                         *args,
# #                         **kwargs,
# #                     )
# #             else:
# #                 self.conversation.append(
# #                     Message(role="assistant", content=message.content)
# #                 )
# #                 self._completed = True

# #     async def handle_tool_call(
# #         self, tool_name: str, tool_arguments: str, tool_id: Optional[str] = None, *args, **kwargs
# #     ) -> ToolResult:
# #         tool = next((t for t in self.config.tools if t.name == tool_name), None)
# #         if tool:
# #             raw_result = await tool.results_function(*args, **kwargs, **json.loads(tool_arguments))
# #             print('raw_result = ', raw_result)
# #             llm_formatted_result = tool.llm_format_function(raw_result)

# #             tool_result = ToolResult(
# #                 raw_result=raw_result,
# #                 llm_formatted_result=llm_formatted_result
# #             )

# #             if tool.stream_function:
# #                 tool_result.stream_result = tool.stream_function(raw_result)

# #             self.conversation.append(
# #                 Message(role="function", name=tool.name, content=llm_formatted_result)
# #             )

# #             return tool_result
# #         else:
# #             raise ValueError(f"Tool {tool_name} not found")

# # # class R2RStreamingAssistant(R2RAssistant):
# # #     async def arun(
# # #         self,
# # #         system_instruction: Optional[str] = None,
# # #         messages: Optional[list[Message]] = None,
# # #         *args,
# # #         **kwargs,
# # #     ) -> AsyncGenerator[dict[str, Any], None]:
# # #         try:
# # #             if system_instruction or not self.conversation:
# # #                 self._setup(system_instruction)

# # #             if messages:
# # #                 self.conversation.extend(messages)

# # #             while not self._completed:
# # #                 generation_config = self.get_generation_config(
# # #                     self.conversation[-1], stream=True
# # #                 )
# # #                 stream = self.llm_provider.get_completion_stream(
# # #                     [
# # #                         ele.model_dump(exclude_none=True)
# # #                         for ele in self.conversation
# # #                     ],
# # #                     generation_config,
# # #                 )
# # #                 async for chunk in self.process_llm_response(
# # #                     stream, *args, **kwargs
# # #                 ):
# # #                     yield chunk
# # #         finally:
# # #             self._completed = False
# # #             self.conversation = []

# # #     def run(
# # #         self, system_instruction, messages, *args, **kwargs
# # #     ) -> Generator[dict[str, Any], None, None]:
# # #         return sync_wrapper(
# # #             self.arun(system_instruction, messages, *args, **kwargs)
# # #         )

# # #     async def process_llm_response(
# # #         self, stream: LLMChatCompletionChunk, *args, **kwargs
# # #     ) -> AsyncGenerator[dict[str, Any], None]:
# # #         function_name = None
# # #         function_arguments = ""
# # #         content_buffer = ""
# # #         current_tool_call: Optional[dict[str, Any]] = None

# # #         for chunk in stream:
# # #             delta = chunk.choices[0].delta
# # #             if delta.tool_calls:
# # #                 for tool_call in delta.tool_calls:
# # #                     if not current_tool_call:
# # #                         current_tool_call = {
# # #                             "name": tool_call.function.name,
# # #                             "arguments": {},
# # #                             "id": tool_call.id
# # #                         }

# # #                     if tool_call.function.arguments:
# # #                         current_tool_call["arguments"].update(json.loads(tool_call.function.arguments))

# # #                     if tool_call.function.name:
# # #                         yield {"type": "tool_call_start", "data": current_tool_call}

# # #             if delta.function_call:
# # #                 if delta.function_call.name:
# # #                     function_name = delta.function_call.name
# # #                 if delta.function_call.arguments:
# # #                     function_arguments += delta.function_call.arguments
# # #             elif delta.content:
# # #                 content_buffer += delta.content
# # #                 yield {"type": "content", "data": delta.content}

# # #             if chunk.choices[0].finish_reason in ["function_call", "tool_calls"]:
# # #                 if not current_tool_call:
# # #                     current_tool_call = {
# # #                         "name": function_name,
# # #                         "arguments": json.loads(function_arguments)
# # #                     }

# # #                 tool_result = await self.handle_tool_call(
# # #                     current_tool_call["name"],
# # #                     json.dumps(current_tool_call["arguments"]),
# # #                     current_tool_call.get("id"),
# # #                     *args,
# # #                     **kwargs
# # #                 )

# # #                 yield {"type": "tool_result", "data": tool_result.dict()}

# # #                 function_name = None
# # #                 function_arguments = ""
# # #                 current_tool_call = None

# # #                 # Continue the conversation
# # #                 await self.arun(*args, **kwargs)

# # #             elif chunk.choices[0].finish_reason == "stop":
# # #                 if content_buffer:
# # #                     self.conversation.append(
# # #                         Message(role="assistant", content=content_buffer)
# # #                     )
# # #                 self._completed = True
# # #                 yield {"type": "end", "data": None}
