"""Abstractions for the LLM model."""

import json
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Optional, Union

from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel, Field

from .base import R2RSerializable

if TYPE_CHECKING:
    from .search import AggregateSearchResult


LLMChatCompletion = ChatCompletion
LLMChatCompletionChunk = ChatCompletionChunk


class RAGCompletion:
    completion: LLMChatCompletion
    search_results: "AggregateSearchResult"

    def __init__(
        self,
        completion: LLMChatCompletion,
        search_results: "AggregateSearchResult",
    ):
        self.completion = completion
        self.search_results = search_results


class GenerationConfig(R2RSerializable):
    _defaults: ClassVar[dict] = {
        "model": "openai/gpt-4o",
        "temperature": 0.1,
        "top_p": 1.0,
        "max_tokens_to_sample": 1024,
        "stream": False,
        "functions": None,
        "tools": None,
        "add_generation_kwargs": None,
        "api_base": None,
    }

    model: str = Field(
        default_factory=lambda: GenerationConfig._defaults["model"]
    )
    temperature: float = Field(
        default_factory=lambda: GenerationConfig._defaults["temperature"]
    )
    top_p: float = Field(
        default_factory=lambda: GenerationConfig._defaults["top_p"]
    )
    max_tokens_to_sample: int = Field(
        default_factory=lambda: GenerationConfig._defaults[
            "max_tokens_to_sample"
        ]
    )
    stream: bool = Field(
        default_factory=lambda: GenerationConfig._defaults["stream"]
    )
    functions: Optional[list[dict]] = Field(
        default_factory=lambda: GenerationConfig._defaults["functions"]
    )
    tools: Optional[list[dict]] = Field(
        default_factory=lambda: GenerationConfig._defaults["tools"]
    )
    add_generation_kwargs: Optional[dict] = Field(
        default_factory=lambda: GenerationConfig._defaults[
            "add_generation_kwargs"
        ]
    )
    api_base: Optional[str] = Field(
        default_factory=lambda: GenerationConfig._defaults["api_base"]
    )

    @classmethod
    def set_default(cls, **kwargs):
        for key, value in kwargs.items():
            if key in cls._defaults:
                cls._defaults[key] = value
            else:
                raise AttributeError(
                    f"No default attribute '{key}' in GenerationConfig"
                )

    def __init__(self, **data):
        model = data.pop("model", None)
        if model is not None:
            super().__init__(model=model, **data)
        else:
            super().__init__(**data)

    def __str__(self):
        return json.dumps(self.to_dict())

    class Config:
        json_schema_extra = {
            "model": "openai/gpt-4o",
            "temperature": 0.1,
            "top_p": 1.0,
            "max_tokens_to_sample": 1024,
            "stream": False,
            "functions": None,
            "tools": None,
            "add_generation_kwargs": None,
            "api_base": None,
        }


class MessageType(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"

    def __str__(self):
        return self.value


class Message(BaseModel):
    role: Union[MessageType, str]
    content: Optional[str] = None
    name: Optional[str] = None
    function_call: Optional[dict[str, Any]] = None
    tool_calls: Optional[list[dict[str, Any]]] = None

    class Config:
        json_schema_extra = {
            "role": "user",
            "content": "This is a test message.",
            "name": None,
            "function_call": None,
            "tool_calls": None,
        }
