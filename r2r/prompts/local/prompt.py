import logging
import os
import json
from typing import Any, Optional

from r2r.core import PromptProvider, Prompt

from typing import Any, Dict

logger = logging.getLogger(__name__)
class DefaultPromptProvider(PromptProvider):
    def __init__(self, file_path: Optional[str] = None):
        self.prompts: Dict[str, Prompt] = {}
        self._load_prompts_from_jsonl(file_path)

    def _load_prompts_from_jsonl(self, file_path: Optional[str] = None):
        if not file_path:
            file_path = os.path.join(os.path.dirname(__file__), "defaults.jsonl")
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    if line.strip():
                        data = json.loads(line)
                        print(data)
                        print(data.get("input_types", {}))
                        self.add_prompt(data["name"], data["template"], data.get("input_types", {}))
        except json.JSONDecodeError as e:
            error_msg = f"Error loading prompts from JSONL file: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    def add_prompt(self, name: str, template: str, input_types: dict[str, str]) -> None:
        if name in self.prompts:
            raise ValueError(f"Prompt '{name}' already exists.")
        self.prompts[name] = Prompt(name=name, template=template, input_types=input_types)

    def get_prompt(self, prompt_name: str, inputs: Optional[dict[str, Any]] = None) -> str:
        if prompt_name not in self.prompts:
            raise ValueError(f"Prompt '{prompt_name}' not found.")
        prompt = self.prompts[prompt_name]
        return prompt.format_prompt(inputs)

    def get_all_prompts(self) -> dict[str, Prompt]:
        return self.prompts
