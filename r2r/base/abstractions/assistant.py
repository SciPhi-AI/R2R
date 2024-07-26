import json
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union

from pydantic import BaseModel

from ..providers.llm import GenerationConfig, LLMProvider
from ..providers.prompt import PromptProvider
from .llm import LLMChatCompletion


class Tool(BaseModel):
    name: str
    description: str
    function: Callable
    parameters: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True


class Message(BaseModel):
    role: str
    content: Optional[str] = None
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class Conversation:
    def __init__(self):
        self.messages: List[Message] = []

    def create_and_add_message(
        self,
        role: str,
        content: Optional[str] = None,
        name: Optional[str] = None,
        function_call: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ):
        message = Message(
            role=role,
            content=content,
            name=name,
            function_call=function_call,
            tool_calls=tool_calls,
        )
        self.add_message(message)

    def add_message(self, message):
        self.messages.append(message)

    def get_messages(self) -> List[Dict[str, Any]]:
        return [msg.dict(exclude_none=True) for msg in self.messages]


class AssistantConfig(BaseModel):
    system_instruction_name: str = "assistant"
    tools: list[Tool] = []
    generation_config: GenerationConfig = GenerationConfig()
    stream: bool = False


class Assistant(ABC):
    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        config: AssistantConfig,
    ):
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider
        self.config = config
        self.conversation = []
        self._completed = False

    def _setup(self, system_instruction: Optional[str] = None):
        self.conversation = [
            Message(
                role="system",
                content=system_instruction
                or self.prompt_provider.get_prompt(
                    self.config.system_instruction_name
                ),
            )
        ]

    @property
    def tools(self) -> list[Tool]:
        return self.config.tools

    @abstractmethod
    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> Union[
        list[LLMChatCompletion], AsyncGenerator[LLMChatCompletion, None]
    ]:
        pass

    @abstractmethod
    async def process_llm_response(
        self,
        response: Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]],
        *args,
        **kwargs,
    ) -> Union[str, AsyncGenerator[str, None]]:
        pass

    async def execute_tool(self, tool_name: str, *args, **kwargs) -> str:
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if tool:
            return await tool.function(*args, **kwargs)
        else:
            return f"Error: Tool {tool_name} not found."

    def get_generation_config(
        self, last_message: Message, stream: bool = False
    ) -> GenerationConfig:
        if (
            last_message.role == "tool" or last_message.role == "function"
        ) and last_message.content != "":
            return GenerationConfig(
                **self.config.generation_config.dict(
                    exclude={"functions", "tools", "stream"}
                ),
                stream=stream,
            )
        return GenerationConfig(
            **self.config.generation_config.dict(
                exclude={"functions", "tools", "stream"}
            ),
            # FIXME: Use tools instead of functions
            # TODO - Investigate why `tools` fails with OpenAI+LiteLLM
            # tools=[
            #     {
            #         "function":{
            #             "name": tool.name,
            #             "description": tool.description,
            #             "parameters": tool.parameters,
            #         },
            #         "type": "function"
            #     }
            #     for tool in self.tools
            # ],
            functions=[
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
                for tool in self.tools
            ],
            stream=stream,
        )

    async def handle_function_call(
        self,
        function_name: str,
        function_arguments: str,
        tool_id: Optional[str] = None,
        *args,
        **kwargs,
    ) -> Union[str, AsyncGenerator[str, None]]:
        tool_args = json.loads(function_arguments)

        (
            self.conversation.append(
                Message(
                    role="assistant",
                    tool_calls=[
                        {
                            "id": tool_id,
                            "function": {
                                "name": function_name,
                                "arguments": function_arguments,
                            },
                        }
                    ],
                )
            )
            if tool_id
            else self.conversation.append(
                Message(
                    role="assistant",
                    function_call={
                        "name": function_name,
                        "arguments": function_arguments,
                    },
                )
            )
        )

        tool_result = await self.execute_tool(
            function_name, *args, **tool_args, **kwargs
        )
        (
            self.conversation.append(
                Message(
                    tool_call_id=tool_id,
                    role="tool",
                    content=str(tool_result),
                    name=function_name,
                )
            )
            if tool_id
            else self.conversation.append(
                Message(
                    role="function",
                    content=str(tool_result),
                    name=function_name,
                )
            )
        )
        return tool_result
