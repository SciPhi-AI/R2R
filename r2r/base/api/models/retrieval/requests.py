from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

# Use absolute import here to avoid circular imports
from r2r.base.agent.base import Message


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


class R2RAgentRequest(BaseModel):
    messages: list["Message"]
    vector_search_settings: Optional[dict] = None
    kg_search_settings: Optional[dict] = None
    rag_generation_config: Optional[dict] = None
    task_prompt_override: Optional[str] = None
    include_title_if_available: Optional[bool] = True
