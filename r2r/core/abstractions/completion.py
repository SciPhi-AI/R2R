from typing import Union

from openai.types import Completion as OpenAICompletion
from openai.types.chat import ChatCompletion

Completion = Union[ChatCompletion, OpenAICompletion]


class RAGCompletion:
    def __init__(
        self, search_results: list, context: str, completion: Completion
    ):
        self.search_results = search_results
        self.context = context
        self.completion = completion

    def to_dict(self):
        return {
            "search_results": self.search_results,
            "context": self.context,
            "completion": self.completion.to_dict(),
        }

    def __repr__(self):
        return f"RAGCompletion(search_results={self.search_results}, context={self.context}, completion={self.completion})"
