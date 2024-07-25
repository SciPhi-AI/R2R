"""Abstractions for the LLM model."""

import json
import re
from typing import (
    TYPE_CHECKING,
    ClassVar,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .search import AggregateSearchResult


LLMChatCompletion = ChatCompletion
LLMChatCompletionChunk = ChatCompletionChunk


class FunctionCall(NamedTuple):
    """A class representing function call to be made by the OpenAI agent."""

    name: str
    arguments: dict[str, str]

    def to_dict(self) -> dict[str, Union[dict[str, str], str]]:
        """Convert the function call to a dictionary."""

        return {
            "name": self.name,
            "arguments": json.dumps(self.arguments),
        }

    @classmethod
    def from_response_dict(
        cls, response_dict: dict[str, str]
    ) -> "FunctionCall":
        """Create a FunctionCall from a response dictionary."""

        def preprocess_json_string(json_string: str) -> str:
            """Preprocess the JSON string to handle control characters."""
            import re

            # Match only the newline characters that are not preceded by a backslash
            json_string = re.sub(r"(?<!\\)\n", "\\n", json_string)
            # Do the same for tabs or any other control characters
            json_string = re.sub(r"(?<!\\)\t", "\\t", json_string)
            return json_string

        if (
            response_dict["name"] == "call-termination"
            and '"result":' in response_dict["arguments"]
        ):
            return cls(
                name=response_dict["name"],
                arguments=FunctionCall.handle_termination(
                    response_dict["arguments"]
                ),
            )
        try:
            return cls(
                name=response_dict["name"],
                arguments=json.loads(
                    preprocess_json_string(response_dict["arguments"])
                ),
            )
        except Exception as e:
            # TODO - put robust infra so this bubbles back up to the agent
            return cls(
                name="error-occurred",
                arguments={"error": f"Error occurred: {e}"},
            )

    @staticmethod
    def handle_termination(arguments: str) -> dict[str, str]:
        """
        Handle the termination message from the conversation.

        Note/FIXME - This is a hacky solution to the problem of parsing Markdown
            with JSON. It needs to be made more robust and generalizable.
            Further, we need to be sure that this is adequate to solve all
            possible problems we might face due to adopting a Markdown return format.
        """

        try:
            return json.loads(arguments)
        except json.decoder.JSONDecodeError as e:
            split_result = arguments.split('{"result":')
            if len(split_result) <= 1:
                raise ValueError(
                    "Invalid arguments for call-termination"
                ) from e
            result_str = split_result[1].strip().replace('"}', "")
            if result_str[0] != '"':
                raise ValueError(
                    "Invalid format for call-termination arguments"
                ) from e
            result_str = result_str[1:]
            return {"result": result_str}

    def __str__(self) -> str:
        return json.dumps(self._asdict())


class LLMChatMessage(BaseModel):
    """Base class for different types of LLM chat messages."""

    role: str
    content: Optional[str] = None
    function_call: Optional[FunctionCall] = (None,)

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


LLMIterationResult = Optional[Tuple[LLMChatMessage, LLMChatMessage]]


class LLMConversation:
    """A class to represent a conversation with the OpenAI API."""

    def __init__(self) -> None:
        super().__init__()
        self._messages: list[LLMChatMessage] = []

    def __len__(self) -> int:
        return len(self._messages)

    @property
    def messages(self) -> Sequence[LLMChatMessage]:
        return self._messages

    def add_message(self, message: LLMChatMessage) -> None:
        """Add a message to the conversation."""

        if not isinstance(message, LLMChatMessage):
            raise Exception(
                f"Message must be of type {LLMChatMessage}, but got {type(message)}"
            )
        self._messages.append(message)

    def to_dictarray(self) -> list[dict[str, any]]:
        """Get the messages for the next completion."""
        return [message.to_dict() for message in self._messages]

    def get_latest_message(self) -> LLMChatMessage:
        """Get the latest message in the conversation."""
        return self._messages[-1]

    def reset_conversation(self) -> None:
        """Reset the conversation."""
        self._messages = []


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


class GenerationConfig(BaseModel):
    _defaults: ClassVar[dict] = {
        "model": "gpt-4o",
        "temperature": 0.1,
        "top_p": 1.0,
        "top_k": 100,
        "max_tokens_to_sample": 1024,
        "stream": False,
        "functions": None,
        "skip_special_tokens": False,
        "stop_token": None,
        "num_beams": 1,
        "do_sample": True,
        "generate_with_chat": False,
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
    top_k: int = Field(
        default_factory=lambda: GenerationConfig._defaults["top_k"]
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
    skip_special_tokens: bool = Field(
        default_factory=lambda: GenerationConfig._defaults[
            "skip_special_tokens"
        ]
    )
    stop_token: Optional[str] = Field(
        default_factory=lambda: GenerationConfig._defaults["stop_token"]
    )
    num_beams: int = Field(
        default_factory=lambda: GenerationConfig._defaults["num_beams"]
    )
    do_sample: bool = Field(
        default_factory=lambda: GenerationConfig._defaults["do_sample"]
    )
    generate_with_chat: bool = Field(
        default_factory=lambda: GenerationConfig._defaults[
            "generate_with_chat"
        ]
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
