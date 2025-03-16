# type: ignore
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
)
from core.base.providers import CompletionProvider, DatabaseProvider

from .base import Tool, ToolResult

logger = logging.getLogger()


class Conversation:
    def __init__(self):
        self.messages: list[Message] = []
        self._lock = asyncio.Lock()

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
    rag_rag_agent_static_prompt: str = "static_rag_agent"
    rag_agent_dynamic_prompt: str = "dynamic_reasoning_rag_agent_prompted"
    stream: bool = False
    include_tools: bool = True
    max_iterations: int = 10

    @classmethod
    def create(cls: Type["AgentConfig"], **kwargs: Any) -> "AgentConfig":
        base_args = cls.model_fields.keys()
        filtered_kwargs = {
            k: v if v != "None" else None
            for k, v in kwargs.items()
            if k in base_args
        }
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
        self.tool_calls: list[dict] = []
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
                        self.config.rag_rag_agent_static_prompt,
                        inputs={
                            "date": str(datetime.now().strftime("%m/%d/%Y"))
                        },
                    )
                    + f"\n Note,you only have {self.config.max_iterations} iterations or tool calls to reach a conclusion before your operation terminates."
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
            and "ollama" in self.rag_generation_config.model
            or not self.config.include_tools
        ):
            return GenerationConfig(
                **self.rag_generation_config.model_dump(
                    exclude={"functions", "tools", "stream"}
                ),
                stream=stream,
            )

        return GenerationConfig(
            **self.rag_generation_config.model_dump(
                exclude={"functions", "tools", "stream"}
            ),
            # FIXME: Use tools instead of functions
            # TODO - Investigate why `tools` fails with OpenAI+LiteLLM
            tools=(
                [
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
                ]
                if self.tools
                else None
            ),
            stream=stream,
        )

    async def handle_function_or_tool_call(
        self,
        function_name: str,
        function_arguments: str,
        tool_id: Optional[str] = None,
        save_messages: bool = True,
        *args,
        **kwargs,
    ) -> ToolResult:
        logger.debug(
            f"Calling function: {function_name}, args: {function_arguments}, tool_id: {tool_id}"
        )
        if tool := next(
            (t for t in self.tools if t.name == function_name), None
        ):
            try:
                function_args = json.loads(function_arguments)

            except JSONDecodeError as e:
                error_message = f"Calling the requested tool '{function_name}' with arguments {function_arguments} failed with `JSONDecodeError`."
                if save_messages:
                    await self.conversation.add_message(
                        Message(
                            role="tool" if tool_id else "function",
                            content=error_message,
                            name=function_name,
                            tool_call_id=tool_id,
                        )
                    )

                # raise R2RException(
                #     message=f"Error parsing function arguments: {e}, agent likely produced invalid tool inputs.",
                #     status_code=400,
                # )

            merged_kwargs = {**kwargs, **function_args}
            try:
                raw_result = await tool.results_function(
                    *args, **merged_kwargs
                )
                llm_formatted_result = tool.llm_format_function(raw_result)
            except Exception as e:
                raw_result = f"Calling the requested tool '{function_name}' with arguments {function_arguments} failed with an exception: {e}."
                logger.error(raw_result)
                llm_formatted_result = raw_result

            tool_result = ToolResult(
                raw_result=raw_result,
                llm_formatted_result=llm_formatted_result,
            )
            if tool.stream_function:
                tool_result.stream_result = tool.stream_function(raw_result)

            if save_messages:
                await self.conversation.add_message(
                    Message(
                        role="tool" if tool_id else "function",
                        content=str(tool_result.llm_formatted_result),
                        name=function_name,
                        tool_call_id=tool_id,
                    )
                )
                # HACK - to fix issues with claude thinking + tool use [https://github.com/anthropics/anthropic-cookbook/blob/main/extended_thinking/extended_thinking_with_tool_use.ipynb]
                if self.rag_generation_config.extended_thinking:
                    await self.conversation.add_message(
                        Message(
                            role="user",
                            content="Continue...",
                        )
                    )

            self.tool_calls.append(
                {
                    "name": function_name,
                    "args": function_arguments,
                }
            )
        return tool_result


# TODO - Move agents to provider pattern
class RAGAgentConfig(AgentConfig):
    rag_rag_agent_static_prompt: str = "static_rag_agent"
    rag_agent_dynamic_prompt: str = "dynamic_reasoning_rag_agent_prompted"
    stream: bool = False
    include_tools: bool = True
    max_iterations: int = 10
    # tools: list[str] = [] # HACK - unused variable.

    # Default RAG tools
    rag_tools: list[str] = [
        "search_file_descriptions",
        "search_file_knowledge",
        "get_file_content",
    ]

    # Default Research tools
    research_tools: list[str] = [
        "rag",
        "reasoning",
        # DISABLED by default
        "critique",
        "python_executor",
    ]

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
