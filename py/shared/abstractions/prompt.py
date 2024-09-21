"""Abstraction for a prompt that can be formatted with inputs."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Prompt(BaseModel):
    """A prompt that can be formatted with inputs."""

    prompt_id: UUID = Field(default_factory=uuid4)
    name: str
    template: str
    input_types: dict[str, str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def format_prompt(self, inputs: dict[str, Any]) -> str:
        self._validate_inputs(inputs)
        formatted_prompt = self.template.format(**inputs)
        return formatted_prompt

    def _validate_inputs(self, inputs: dict[str, Any]) -> None:
        for var, expected_type_name in self.input_types.items():
            expected_type = self._convert_type(expected_type_name)
            if var not in inputs:
                raise ValueError(f"Missing input: {var}")
            if not isinstance(inputs[var], expected_type):
                raise TypeError(
                    f"Input '{var}' must be of type {expected_type.__name__}, got {type(inputs[var]).__name__} instead."
                )

    def _convert_type(self, type_name: str) -> type:
        type_mapping = {"int": int, "str": str}
        return type_mapping.get(type_name, str)
