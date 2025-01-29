import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from json import JSONDecodeError
from typing import Any, AsyncGenerator, Optional, Type

from pydantic import BaseModel

from core.base.abstractions import (
    GenerationConfig,
    LLMChatCompletion,
    Message,
    MessageType,
    R2RException,
)
from core.base.providers import CompletionProvider, DatabaseProvider

from .base import Tool, ToolResult

logger = logging.getLogger()


class Conversation:
    def __init__(self):
        self.messages: list[Message] = []
        self._lock = asyncio.Lock()

    def create_and_add_message(
        self,
        role: MessageType | str,
        content: Optional[str] = None,
        name: Optional[str] = None,
        function_call: Optional[dict[str, Any]] = None,
        tool_calls: Optional[list[dict[str, Any]]] = None,
    ):
        message = Message(
            role=role,
            content=content,
            name=name,
            function_call=function_call,
            tool_calls=tool_calls,
        )
        self.add_message(message)

    async def add_message(self, message):
        async with self._lock:
            self.messages.append(message)

    async def get_messages(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [
                {**msg.model_dump(exclude_none=True), "role": str(msg.role)}
                for msg in self.messages
            ]


# TODO - Move agents to provider pattern
class AgentConfig(BaseModel):
    system_instruction_name: str = "rag_agent"
    tools: list[str] = ["search"]
    tool_names: Optional[list[str]] = None
    generation_config: GenerationConfig = GenerationConfig()
    stream: bool = False

    @classmethod
    def create(cls: Type["AgentConfig"], **kwargs: Any) -> "AgentConfig":
        base_args = cls.model_fields.keys()
        filtered_kwargs = {
            k: v if v != "None" else None
            for k, v in kwargs.items()
            if k in base_args
        }
        filtered_kwargs["tools"] = kwargs.get("tools", None) or kwargs.get(
            "tool_names", None
        )
        return cls(**filtered_kwargs)  # type: ignore


class Agent(ABC):
    def __init__(
        self,
        llm_provider: CompletionProvider,
        database_provider: DatabaseProvider,
        config: AgentConfig,
        rag_generation_config: GenerationConfig,
    ):
        self.llm_provider = llm_provider
        self.database_provider: DatabaseProvider = database_provider
        self.config = config
        self.conversation = Conversation()
        self._completed = False
        self._tools: list[Tool] = []
        self.rag_generation_config = rag_generation_config
        self._register_tools()

    @abstractmethod
    def _register_tools(self):
        pass

    async def _setup(
        self, system_instruction: Optional[str] = None, *args, **kwargs
    ):
        await self.conversation.add_message(
            Message(
                role="system",
                content=system_instruction
                or (
                    await self.database_provider.prompts_handler.get_cached_prompt(
                        self.config.system_instruction_name,
                        inputs={"date": str(datetime.now().isoformat())},
                    )
                ),
            )
        )

    @property
    def tools(self) -> list[Tool]:
        return self._tools

    @tools.setter
    def tools(self, tools: list[Tool]):
        self._tools = tools

    @abstractmethod
    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> list[LLMChatCompletion] | AsyncGenerator[LLMChatCompletion, None]:
        pass

    @abstractmethod
    async def process_llm_response(
        self,
        response: Any,
        *args,
        **kwargs,
    ) -> None | AsyncGenerator[str, None]:
        pass

    async def execute_tool(self, tool_name: str, *args, **kwargs) -> str:
        if tool := next((t for t in self.tools if t.name == tool_name), None):
            return await tool.results_function(*args, **kwargs)
        else:
            return f"Error: Tool {tool_name} not found."

    def get_generation_config(
        self, last_message: dict, stream: bool = False
    ) -> GenerationConfig:
        if (
            last_message["role"] in ["tool", "function"]
            and last_message["content"] != ""
        ):
            return GenerationConfig(
                **self.rag_generation_config.model_dump(
                    exclude={"functions", "tools", "stream"}
                ),
                stream=stream,
            )

        if (
            "azure" in self.rag_generation_config.model
            or "anthropic" in self.rag_generation_config.model
            or "openai" in self.rag_generation_config.model
            or "deepseek" in self.rag_generation_config.model
        ):
            # return with tools
            return GenerationConfig(
                **self.rag_generation_config.model_dump(
                    exclude={"functions", "tools", "stream"}
                ),
                # FIXME: Use tools instead of functions
                # TODO - Investigate why `tools` fails with OpenAI+LiteLLM
                tools=[
                    {
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                        },
                        "type": "function",
                        "name": tool.name,
                    }
                    for tool in self.tools
                ],
                stream=stream,
            )
        else:
            return GenerationConfig(
                **self.rag_generation_config.model_dump(
                    exclude={"functions", "tools", "stream"}
                ),
                # FIXME: Use tools instead of functions
                # TODO - Investigate why `tools` fails with ollama and the like
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

    async def handle_function_or_tool_call(
        self,
        function_name: str,
        function_arguments: str,
        tool_id: Optional[str] = None,
        *args,
        **kwargs,
    ) -> ToolResult:
        logger.info(
            f"Calling function: {function_name}, args: {function_arguments}, tool_id: {tool_id}"
        )
        if tool := next(
            (t for t in self.tools if t.name == function_name), None
        ):
            try:
                function_args = json.loads(function_arguments)
            except JSONDecodeError as e:
                error_message = f"The requested tool '{function_name}' is not available with arguments {function_arguments} failed."
                tool_result = ToolResult(
                    raw_result=error_message,
                    llm_formatted_result=error_message,
                )
                await self.conversation.add_message(
                    Message(
                        role="tool" if tool_id else "function",
                        content=str(tool_result.llm_formatted_result),
                        name=function_name,
                        tool_call_id=tool_id,
                    )
                )

                raise R2RException(
                    message=f"Error parsing function arguments: {e}, agent likely produced invalid tool inputs.",
                    status_code=400,
                )

            merged_kwargs = {**kwargs, **function_args}
            raw_result = await tool.results_function(*args, **merged_kwargs)
            llm_formatted_result = tool.llm_format_function(raw_result)
            tool_result = ToolResult(
                raw_result=raw_result,
                llm_formatted_result=llm_formatted_result,
            )
            if tool.stream_function:
                tool_result.stream_result = tool.stream_function(raw_result)

            await self.conversation.add_message(
                Message(
                    role="tool" if tool_id else "function",
                    content=str(tool_result.llm_formatted_result),
                    name=function_name,
                    tool_call_id=tool_id,
                )
            )

        return tool_result
