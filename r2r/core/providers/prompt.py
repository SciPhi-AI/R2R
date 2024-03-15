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


class DefaultPromptProvider(PromptProvider):
    def __init__(self) -> None:
        self.prompts: dict[str, str] = {}

    def add_prompt(self, prompt_name: str, prompt: str) -> None:
        self.prompts[prompt_name] = prompt

    def get_prompt(
        self, prompt_name: str, inputs: Optional[dict[str, Any]] = None
    ) -> str:
        prompt = self.prompts.get(prompt_name)
        if prompt is None:
            raise ValueError(f"Prompt '{prompt_name}' not found.")
        return prompt.format(**(inputs or {}))

    def set_prompt(self, prompt_name: str, prompt: str) -> None:
        if prompt_name not in self.prompts:
            raise ValueError(f"Prompt '{prompt_name}' not found.")
        self.prompts[prompt_name] = prompt

    def get_all_prompts(self) -> dict[str, str]:
        return self.prompts.copy()
