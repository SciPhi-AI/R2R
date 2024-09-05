from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel

from core.base.api.models.base import ResultsWrapper

class KGCreationResponse(BaseModel):
    message: str
    task_id: UUID

class KGEnrichmentResponse(BaseModel):
    message: str
    task_id: UUID

WrappedKGCreationResponse = ResultsWrapper[KGCreationResponse]
WrappedKGEnrichmentResponse = ResultsWrapper[KGEnrichmentResponse]
