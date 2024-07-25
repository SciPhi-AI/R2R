from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

from ..providers.llm import GenerationConfig, LLMProvider
from ..providers.prompt import PromptProvider


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


class Conversation:
    def __init__(self):
        self.messages: List[Message] = []

    def create_and_add_message(
        self,
        role: str,
        content: Optional[str] = None,
        name: Optional[str] = None,
        function_call: Optional[Dict[str, Any]] = None,
    ):
        message = Message(
            role=role,
            content=content,
            name=name,
            function_call=function_call,
        )
        self.add_message(message)

    def add_message(self, message):
        self.messages.append(message)

    def get_messages(self) -> List[Dict[str, Any]]:
        return [msg.dict(exclude_none=True) for msg in self.messages]


class AssistantConfig(BaseModel):
    system_instruction_name: str = "assistant"
    tools: List[Tool] = Field(default_factory=list)
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
        self.conversation = Conversation()

    def _setup(self, system_instruction: Optional[str] = None):
        self.conversation.create_and_add_message(
            "system",
            system_instruction
            or self.prompt_provider.get_prompt(
                self.config.system_instruction_name
            ),
        )

    @property
    def tools(self) -> Sequence[Tool]:
        return self.config.tools

    @abstractmethod
    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ):
        pass

    @abstractmethod
    async def process_llm_response(self, response: Dict[str, Any]) -> str:
        pass

    async def execute_tool(self, tool_name: str, **kwargs) -> str:
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if tool:
            return await tool.function(**kwargs)
        else:
            return f"Error: Tool {tool_name} not found."
