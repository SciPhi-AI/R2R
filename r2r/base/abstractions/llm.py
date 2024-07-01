"""Abstractions for the LLM model."""

from typing import TYPE_CHECKING, Optional

from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel

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


class GenerationConfig(BaseModel):
    temperature: float = 0.1
    top_p: float = 1.0
    top_k: int = 100
    max_tokens_to_sample: int = 1_024
    model: str = "gpt-4o"
    stream: bool = False
    functions: Optional[list[dict]] = None
    skip_special_tokens: bool = False
    stop_token: Optional[str] = None
    num_beams: int = 1
    do_sample: bool = True
    # Additional args to pass to the generation config
    generate_with_chat: bool = False
    add_generation_kwargs: Optional[dict] = {}
    api_base: Optional[str] = None
