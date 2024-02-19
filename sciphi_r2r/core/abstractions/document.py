from pydantic import BaseModel


class BasicDocument(BaseModel):
    id: str
    text: str
    metadata: dict
