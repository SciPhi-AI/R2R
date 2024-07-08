import logging
import os
from abc import abstractmethod
from pathlib import Path
from typing import Any, Optional

from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class PromptConfig(ProviderConfig):
    # TODO - Replace this with a database
    file_path: Path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "providers",
        "prompts",
        "defaults.jsonl",
    )

    def validate(self) -> None:
        pass

    @property
    def supported_providers(self) -> list[str]:
        # Return a list of supported prompt providers
        return ["r2r"]


class PromptProvider(Provider):
    def __init__(self, config: Optional[PromptConfig] = None):
        if config is None:
            config = PromptConfig()
        elif not isinstance(config, PromptConfig):
            raise ValueError(
                "PromptProvider must be initialized with a `PromptConfig`."
            )
        logger.info(f"Initializing PromptProvider with config {config}.")
        super().__init__(config)

    @abstractmethod
    def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> None:
        pass

    @abstractmethod
    def get_prompt(
        self, prompt_name: str, inputs: Optional[dict[str, Any]] = None
    ) -> str:
        pass

    @abstractmethod
    def get_all_prompts(self) -> dict[str, str]:
        pass

    @abstractmethod
    def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        pass

    def _get_message_payload(
        self, system_prompt: str, task_prompt: str
    ) -> dict:
        return [
            {
                "role": "system",
                "content": system_prompt,
            },
            {"role": "user", "content": task_prompt},
        ]
