"""
Abstractions for LLM completions.
"""

import json
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from .search import AggregateSearchResult


class MessageType(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"

    def __str__(self):
        return self.value


class CompletionRecord(BaseModel):
    message_id: UUID
    message_type: MessageType
    timestamp: datetime = datetime.now()
    feedback: Optional[List[str]] = None
    score: Optional[List[float]] = None
    completion_start_time: Optional[datetime] = None
    completion_end_time: Optional[datetime] = None
    search_query: Optional[str] = None
    search_results: Optional[AggregateSearchResult] = None
    llm_response: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def to_dict(self):
        def serialize(obj):
            if isinstance(obj, UUID):
                return str(obj)
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, Enum):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize(v) for v in obj]
            elif hasattr(obj, "dict"):
                return serialize(obj.dict())
            return obj

        return serialize(
            {
                "message_id": self.message_id,
                "message_type": self.message_type,
                "timestamp": self.timestamp,
                "feedback": self.feedback,
                "score": self.score,
                "completion_start_time": self.completion_start_time,
                "completion_end_time": self.completion_end_time,
                "search_query": self.search_query,
                "search_results": self.search_results,
                "llm_response": self.llm_response,
            }
        )

    def to_json(self):
        return json.dumps(self.to_dict())
