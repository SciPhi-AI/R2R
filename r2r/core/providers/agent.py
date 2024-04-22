from abc import ABC, abstractmethod
from typing import Any, Dict

from .llm import LLMProvider
from .prompt import PromptProvider


class AgentProvider(ABC):
    def __init__(
        self, llm_provider: LLMProvider, prompt_provider: PromptProvider
    ):
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider
        self.agents: Dict[str, Any] = {}

    @abstractmethod
    def create_agent(self, agent_name: str, agent_config: dict) -> None:
        pass

    @abstractmethod
    def get_agent(self, agent_name: str) -> Any:
        pass

    @abstractmethod
    def remove_agent(self, agent_name: str) -> None:
        pass

    @abstractmethod
    def get_all_agents(self) -> Dict[str, Any]:
        pass
