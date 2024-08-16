from typing import List, Optional

from pydantic import BaseModel


class KGEnrichGraphRequest(BaseModel):
    query: str
    entity_types: Optional[List[str]] = None
    relationships: Optional[List[str]] = None
    generation_config: Optional[dict] = None
