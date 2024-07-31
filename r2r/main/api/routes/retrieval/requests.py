from typing import Optional

from pydantic import BaseModel

from r2r.base import Message


class R2RSearchRequest(BaseModel):
    query: str
    vector_search_settings: Optional[dict] = None
    kg_search_settings: Optional[dict] = None


class R2RRAGRequest(BaseModel):
    query: str
    vector_search_settings: Optional[dict] = None
    kg_search_settings: Optional[dict] = None
    rag_generation_config: Optional[dict] = None
    task_prompt_override: Optional[str] = None
    include_title_if_available: Optional[bool] = True


class R2REvalRequest(BaseModel):
    query: str
    context: str
    completion: str


class R2RRAGAgentRequest(BaseModel):
    messages: list[Message]
    vector_search_settings: Optional[dict] = None
    kg_search_settings: Optional[dict] = None
    rag_generation_config: Optional[dict] = None
    task_prompt_override: Optional[str] = None
    include_title_if_available: Optional[bool] = True
