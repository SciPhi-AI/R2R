from pydantic import BaseModel


class DocumentPage(BaseModel):
    doc_id: str
    page_num: int
    text: str
    metadata: dict
