from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class ChunkResponse(BaseModel):
    document_id: UUID
    extraction_id: UUID
    user_id: UUID
    collection_ids: list[UUID]
    text: str
    metadata: dict[str, Any]
    vector: Optional[list[float]] = None
