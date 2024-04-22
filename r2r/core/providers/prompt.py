from abc import ABC, abstractmethod
from typing import Any, Optional


class PromptProvider(ABC):
    @abstractmethod
    def add_prompt(self, prompt_name: str, prompt: str) -> None:
        pass

    @abstractmethod
    def get_prompt(
        self, prompt_name: str, inputs: Optional[dict[str, Any]] = None
    ) -> str:
        pass

    @abstractmethod
    def get_all_prompts(self) -> dict[str, str]:
        pass