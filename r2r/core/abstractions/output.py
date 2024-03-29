from typing import Optional

from openai.types.chat import ChatCompletion


class RAGPipelineOutput:
    def __init__(
        self,
        search_results: list,
        context: Optional[str] = None,
        completion: Optional[ChatCompletion] = None,
    ):
        self.search_results = search_results
        self.context = context
        self.completion = completion

    def to_dict(self):
        return {
            "search_results": self.search_results,
            "context": self.context,
            "completion": (
                self.completion.to_dict() if self.completion else None
            ),
        }

    def __repr__(self):
        return f"RAGPipelineOutput(search_results={self.search_results}, context={self.context}, completion={self.completion})"
