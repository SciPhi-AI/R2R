from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

from ..providers.llm import GenerationConfig, LLMProvider


class Tool(BaseModel):
    name: str
    description: str
    function: Callable

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
    system_instruction: str
    tools: List[Tool] = Field(default_factory=list)
    generation_config: GenerationConfig = GenerationConfig()


class Assistant(ABC):
    def __init__(
        self,
        instructions: str,
        llm_provider: LLMProvider,
        config: AssistantConfig,
    ):
        self.instructions = instructions
        self.llm_provider = llm_provider
        self.config = config
        self.conversation = Conversation()
        self.completed = False
        self._setup()

    def _setup(self):
        self.conversation.add_message("system", self.config.system_instruction)
        self.conversation.add_message("system", self.instructions)

    @property
    def tools(self) -> Sequence[Tool]:
        return self.config.tools

    @abstractmethod
    async def run(self) -> str:
        pass

    @abstractmethod
    async def process_llm_response(self, response: Dict[str, Any]) -> str:
        pass

    def add_user_message(self, content: str):
        self.conversation.add_message("user", content)

    async def search(self, query: str) -> str:
        # Implement the search functionality here
        # This could involve calling an external search API or querying a local database
        return f"Simulated search results for: {query}"

    async def execute_tool(self, tool_name: str, **kwargs) -> str:
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if tool:
            return await tool.function(**kwargs)
        else:
            return f"Error: Tool {tool_name} not found."
