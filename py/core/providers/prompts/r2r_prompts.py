import logging
import os
from pathlib import Path
from typing import Any, Optional

import toml
import yaml

from core.base import Prompt, PromptConfig, PromptProvider

logger = logging.getLogger(__name__)


class R2RPromptProvider(PromptProvider):
    def __init__(self, config: PromptConfig = PromptConfig()):
        self.prompts: dict[str, Prompt] = {}
        self._load_prompts_from_yaml_directory(directory_path=config.file_path)
        super().__init__(config)

    def _load_prompts_from_yaml_directory(
        self, directory_path: Optional[Path] = None
    ):
        if not directory_path:
            directory_path = Path(os.path.dirname(__file__)) / "defaults"

        if not directory_path.is_dir():
            raise ValueError(
                f"The specified path is not a directory: {directory_path}"
            )

        logger.info(f"Loading prompts from {directory_path}")
        for yaml_file in directory_path.glob("*.yaml"):
            logger.debug(f"Loaded prompts from {yaml_file}")
            try:
                with open(yaml_file, "r") as file:
                    data = yaml.safe_load(file)
                    for name, prompt_data in data.items():
                        self.add_prompt(
                            name,
                            prompt_data["template"],
                            prompt_data.get("input_types", {}),
                        )
            except toml.TomlDecodeError as e:
                error_msg = (
                    f"Error loading prompts from TOML file {yaml_file}: {e}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            except KeyError as e:
                error_msg = f"Missing key in TOML file {yaml_file}: {e}"
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
