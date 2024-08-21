from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from core.base.api.models.base import ResultsWrapper
from pydantic import BaseModel


class KGEnrichmentResponse(BaseModel):
    enriched_content: Dict[str, Any]


WrappedKGEnrichmentResponse = ResultsWrapper[KGEnrichmentResponse]
