from pydantic import BaseModel


class DocumentPage(BaseModel):
    document_id: str
    page_number: int
    text: str
    metadata: dict
