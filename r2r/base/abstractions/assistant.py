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

    def add_message(
        self,
        role: str,
        content: Optional[str] = None,
        name: Optional[str] = None,
        function_call: Optional[Dict[str, Any]] = None,
    ):
        self.messages.append(
            Message(
                role=role,
                content=content,
                name=name,
                function_call=function_call,
            )
        )

    def get_messages(self) -> List[Dict[str, Any]]:
        return [msg.dict(exclude_none=True) for msg in self.messages]


class AssistantConfig(BaseModel):
    system_instruction_name: str = "rag_assistant"
    tools: List[Tool] = Field(default_factory=list)
    generation_config: GenerationConfig = GenerationConfig()


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
        self.completed = False
        self._setup()

    def _setup(self):
        self.conversation.add_message(
            "system",
            self.prompt_provider.get_prompt(
                self.config.system_instruction_name
            ),
        )

    @property
    def tools(self) -> Sequence[Tool]:
        return self.config.tools

    @abstractmethod
    async def arun(self) -> str:
        pass

    @abstractmethod
    async def process_llm_response(self, response: Dict[str, Any]) -> str:
        pass

    def add_user_message(self, content: str):
        self.conversation.add_message("user", content)

    async def execute_tool(self, tool_name: str, **kwargs) -> str:
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if tool:
            return await tool.function(**kwargs)
        else:
            return f"Error: Tool {tool_name} not found."
