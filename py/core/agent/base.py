import json
import asyncio
import logging
from abc import ABCMeta
from typing import Optional

from core.base import AsyncSyncMeta, LLMChatCompletion, Message, syncable
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

    async def process_llm_response(self, response: LLMChatCompletion, *args, **kwargs) -> None:
        if not self._completed:
            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            
            if finish_reason == "stop":
                self._completed = True
            
            # First handle thinking blocks if present (which don't include tool_use)
            if hasattr(message, "structured_content") and message.structured_content:
                # Check if structured_content contains any tool_use blocks
                has_tool_use = any(block.get("type") == "tool_use" for block in message.structured_content)
                if not has_tool_use and message.tool_calls:
                    # If it has thinking but no tool_use, add a separate message for tool_use
                    assistant_msg = Message(
                        role="assistant",
                        content=message.structured_content
                    )
                    await self.conversation.add_message(assistant_msg)
                    
                    # Add explicit tool_use blocks in a separate message
                    tool_uses = []
                    for tool_call in message.tool_calls:
                        tool_uses.append({
                            "type": "tool_use",
                            "id": tool_call.id,
                            "name": tool_call.function.name,
                            "input": json.loads(tool_call.function.arguments)
                        })
                    
                    # Add tool_use blocks as a separate assistant message
                    if tool_uses:
                        await self.conversation.add_message(
                            Message(role="assistant", content=tool_uses)
                        )
                else:
                    # If it already has tool_use or no tool_calls, add as is
                    assistant_msg = Message(
                        role="assistant",
                        content=message.structured_content
                    )
                    await self.conversation.add_message(assistant_msg)
            elif message.content:
                # For regular text content
                await self.conversation.add_message(
                    Message(role="assistant", content=message.content)
                )
                
                # If there are tool calls, add them as a separate message with tool_use blocks
                if message.tool_calls:
                    tool_uses = []
                    for tool_call in message.tool_calls:
                        tool_uses.append({
                            "type": "tool_use",
                            "id": tool_call.id,
                            "name": tool_call.function.name,
                            "input": json.loads(tool_call.function.arguments)
                        })
                    
                    await self.conversation.add_message(
                        Message(role="assistant", content=tool_uses)
                    )
            
            # Now process the tool calls - this remains mostly unchanged
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    await self.handle_function_or_tool_call(
                        tool_call.function.name,
                        tool_call.function.arguments,
                        tool_id=tool_call.id,
                        *args,
                        **kwargs,
                    )