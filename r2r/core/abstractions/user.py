import uuid
from typing import List
from pydantic import BaseModel

class UserStats(BaseModel):
    user_id: uuid.UUID
    num_files: int
    total_size: int
    document_ids: List[uuid.UUID]