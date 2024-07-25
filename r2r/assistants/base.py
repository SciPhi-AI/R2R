import json
from abc import ABCMeta
from typing import Any, Optional

from r2r.base import Assistant, AsyncSyncMeta, GenerationConfig, syncable

# from .base import AsyncSyncMeta, syncable


class CombinedMeta(AsyncSyncMeta, ABCMeta):
    pass


class R2RAssistant(Assistant, metaclass=CombinedMeta):

    @syncable
    async def arun(self, user_message: Optional[str] = None) -> str:
        # Example usage
        if user_message:
            self.add_user_message(user_message)

        self.completed = False
        while not self.completed:
            generation_config_with_functions = GenerationConfig(
                **self.config.generation_config.model_dump(
                    exclude={"functions"}
                ),
                functions=[
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                    for tool in self.tools
                ]
            )
            response = await self.llm_provider.aget_completion(
                self.conversation.get_messages(),
                generation_config_with_functions,
            )
            result = await self.process_llm_response(response)
            if self.completed:
                return result

    async def process_llm_response(self, response: dict[str, Any]) -> str:
        message = response.choices[0].message
        if message.function_call:
            tool_name = message.function_call.name
            tool_args = json.loads(message.function_call.arguments)

            self.conversation.add_message(
                "assistant",
                function_call={
                    "name": tool_name,
                    "arguments": message.function_call.arguments,
                },
            )

            tool_result = await self.execute_tool(tool_name, **tool_args)
            self.conversation.add_message(
                "function", content=tool_result, name=tool_name
            )

            return await self.arun()  # Continue the conversation
        else:
            content = message.content
            self.conversation.add_message("assistant", content=content)
            self.completed = True
            return content
