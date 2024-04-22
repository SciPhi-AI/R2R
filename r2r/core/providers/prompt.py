from abc import abstractmethod
from typing import Any, List, Optional

from .base import Provider, ProviderConfig


class PromptProviderConfig(ProviderConfig):
    def validate(self) -> None:
        pass

    @property
    def supported_providers(self) -> List[str]:
        # Return a list of supported prompt providers
        return ["default_prompt_provider"]


class PromptProvider(Provider):
    def __init__(self, config: Optional[PromptProviderConfig] = None):
        super().__init__(config)

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
