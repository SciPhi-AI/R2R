from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class ChunkResponse(BaseModel):
    document_id: UUID
    id: UUID
    collection_ids: list[UUID]
    text: str
    metadata: dict[str, Any]
    vector: Optional[list[float]] = None

class ChunkIngestionResponse(BaseModel):
    """Response model for chunk ingestion"""
    message: str 
    document_id: UUID