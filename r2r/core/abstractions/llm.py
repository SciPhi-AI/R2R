from typing import Optional

from openai.types.chat import ChatCompletion, ChatCompletionChunk

from .search import SearchResult

LLMChatCompletion = ChatCompletion
LLMChatCompletionChunk = ChatCompletionChunk


class RAGPipeOutput:
    def __init__(
        self,
        search_results: list[SearchResult],
        context: Optional[str] = None,
        completion: Optional[LLMChatCompletion] = None,
        metadata: Optional[dict[str, str]] = None,
    ):
        self.search_results = search_results
        self.context = context or "N/A"
        self.completion = completion
        self.metadata = metadata or {}

    def dict(self):
        return {
            "search_results": self.search_results,
            "context": self.context,
            "completion": (
                self.completion.dict() if self.completion else None
            ),
            "metadata": self.metadata,
        }

    def __repr__(self):
        return f"RAGPipeOutput(search_results={self.search_results}, context={self.context}, completion={self.completion}, metadata={self.metadata})"
