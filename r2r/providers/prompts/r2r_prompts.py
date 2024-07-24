import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from r2r.base import Prompt, PromptConfig, PromptProvider

logger = logging.getLogger(__name__)


class R2RPromptProvider(PromptProvider):
    def __init__(self, config: PromptConfig = PromptConfig()):
        self.prompts: dict[str, Prompt] = {}
        self._load_prompts_from_jsonl(file_path=config.file_path)
        super().__init__(config)

    def _load_prompts_from_jsonl(self, file_path: Optional[Path] = None):
        if not file_path:
            file_path = os.path.join(
                os.path.dirname(__file__), "defaults.jsonl"
            )
        try:
            with open(file_path, "r") as file:
                for line in file:
                    if line.strip():
                        data = json.loads(line)
                        self.add_prompt(
                            data["name"],
                            data["template"],
                            data.get("input_types", {}),
                        )
        except json.JSONDecodeError as e:
            error_msg = f"Error loading prompts from JSONL file: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> None:
        if name in self.prompts:
            raise ValueError(f"Prompt '{name}' already exists.")
        self.prompts[name] = Prompt(
            name=name, template=template, input_types=input_types
        )

    def get_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> str:
        if prompt_name not in self.prompts:
            raise ValueError(f"Prompt '{prompt_name}' not found.")
        existing_types = self.prompts[prompt_name].input_types
        prompt = (
            Prompt(
                name=prompt_name,
                template=prompt_override,
                input_types=existing_types,
            )
            if prompt_override
            else self.prompts[prompt_name]
        )
        if inputs is None:
            return prompt.template
        return prompt.format_prompt(inputs)

    def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        if name not in self.prompts:
            raise ValueError(f"Prompt '{name}' not found.")
        if template:
            self.prompts[name].template = template
        if input_types:
            self.prompts[name].input_types = input_types

    def get_all_prompts(self) -> dict[str, Prompt]:
        return self.prompts
