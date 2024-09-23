import logging
from abc import abstractmethod
from pathlib import Path
from typing import Any, Optional

from core.base.abstractions import Prompt

from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class PromptConfig(ProviderConfig):
    default_system_name: str = "default_system"
    default_task_name: str = "default_rag"

    # TODO - Replace this with a database
    file_path: Optional[Path] = None

    def validate_config(self) -> None:
        pass

    @property
    def supported_providers(self) -> list[str]:
        # Return a list of supported prompt providers
        return ["r2r"]


class PromptProvider(Provider):
    def __init__(self, config: PromptConfig):
        logger.info(f"Initializing PromptProvider with config {config}.")
        super().__init__(config)
        self.config: PromptConfig = config

    @abstractmethod
    async def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> None:
        pass

    @abstractmethod
    def get_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> str:
        pass

    @abstractmethod
    def get_all_prompts(self) -> dict[str, Prompt]:
        pass

    @abstractmethod
    async def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        pass

    @abstractmethod
    async def delete_prompt(self, name: str) -> None:
        pass

    def _get_message_payload(
        self,
        system_prompt_name: Optional[str] = None,
        system_role: str = "system",
        system_inputs: dict = {},
        system_prompt_override: Optional[str] = None,
        task_prompt_name: Optional[str] = None,
        task_role: str = "user",
        task_inputs: dict = {},
        task_prompt_override: Optional[str] = None,
    ) -> list[dict]:
        system_prompt = system_prompt_override or self.get_prompt(
            system_prompt_name or self.config.default_system_name,
            system_inputs,
            prompt_override=system_prompt_override,
        )
        task_prompt = self.get_prompt(
            task_prompt_name or self.config.default_task_name,
            task_inputs,
            prompt_override=task_prompt_override,
        )
        return [
            {
                "role": system_role,
                "content": system_prompt,
            },
            {"role": task_role, "content": task_prompt},
        ]
