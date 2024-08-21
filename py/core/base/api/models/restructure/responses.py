from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from core.base.api.models.base import ResultsWrapper
from pydantic import BaseModel


class KGEnrichementResponse(BaseModel):
    enriched_content: Dict[str, Any]


WrappedKGEnrichementResponse = ResultsWrapper[KGEnrichementResponse]
