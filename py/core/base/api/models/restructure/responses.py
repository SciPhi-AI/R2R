from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel

from core.base.api.models.base import ResultsWrapper


class KGEnrichmentResponse(BaseModel):
    enriched_content: Dict[str, Any]


WrappedKGEnrichmentResponse = ResultsWrapper[KGEnrichmentResponse]
