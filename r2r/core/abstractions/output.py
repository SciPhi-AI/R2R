from typing import Optional

from openai.types.chat import ChatCompletion, ChatCompletionChunk

from ..abstractions.vector import VectorSearchResult

LLMChatCompletion = ChatCompletion
LLMChatCompletionChunk = ChatCompletionChunk


class RAGPipelineOutput:
    def __init__(
        self,
        search_results: list[VectorSearchResult],
        context: Optional[str] = None,
        completion: Optional[LLMChatCompletion] = None,
        metadata: Optional[dict[str, str]] = None,
    ):
        self.search_results = search_results
        self.context = context or "N/A"
        self.completion = completion
        self.metadata = metadata or {}

    def to_dict(self):
        return {
            "search_results": self.search_results,
            "context": self.context,
            "completion": (
                self.completion.to_dict() if self.completion else None
            ),
            "metadata": self.metadata,
        }

    def __repr__(self):
        return f"RAGPipelineOutput(search_results={self.search_results}, context={self.context}, completion={self.completion}, metadata={self.metadata})"
