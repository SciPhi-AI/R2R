import uuid
from typing import Optional

from pydantic import BaseModel


class R2RUpdateFilesRequest(BaseModel):
    metadatas: Optional[list[dict]] = None
    document_ids: Optional[list[uuid.UUID]] = None
    chunking_config_override: Optional[dict] = None


class R2RIngestFilesRequest(BaseModel):
    document_ids: Optional[list[uuid.UUID]] = None
    metadatas: Optional[list[dict]] = None
    versions: Optional[list[str]] = None
    chunking_config_override: Optional[dict] = None
