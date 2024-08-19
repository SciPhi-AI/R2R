from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

from r2r.base.api.models.base import ResultsWrapper


class KGEnrichementResponse(BaseModel):
    enriched_content: Dict[str, Any]


WrappedKGEnrichementResponse = ResultsWrapper[KGEnrichementResponse]