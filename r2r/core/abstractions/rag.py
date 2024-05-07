from typing import Any, Optional

from .search import SearchResult
from .llm import LLMChatCompletion
from pydantic import BaseModel


class RAGRequest(BaseModel):
    message: str
    # TODO - change `Any` to a more specific type
    # e.g. something which can be cast to a string
    inputs: dict[str, Any] 


class RAGResult:
    def __init__(
        self,
        context: Optional[str] = None,
        completion: Optional[LLMChatCompletion] = None,
        metadata: Optional[dict[str, str]] = None,
    ):
        self.context = context or "N/A"
        self.completion = completion
        self.metadata = metadata or {}