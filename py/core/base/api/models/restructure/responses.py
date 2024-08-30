from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel

from core.base.api.models.base import ResultsWrapper


class KGEnrichmentResponse(BaseModel):
    message: str
    task_id: UUID


WrappedKGEnrichmentResponse = ResultsWrapper[KGEnrichmentResponse]
