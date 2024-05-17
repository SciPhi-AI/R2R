import uuid
from enum import Enum
from typing import Union

from pydantic import BaseModel

DataType = Union[str, bytes]


class DocumentType(Enum):
    CSV = "csv"
    DOCX = "docx"
    HTML = "html"
    JSON = "json"
    MD = "md"
    PDF = "pdf"
    PPTX = "pptx"
    TXT = "txt"
    XLSX = "xlsx"
    GIF = "gif"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    SVG = "svg"
    MP3 = "mp3"
    MP4 = "mp4"


class Document(BaseModel):
    id: uuid.UUID
    type: DocumentType
    data: DataType
    metadata: dict


class ExtractionType(Enum):
    TXT = "txt"
    IMG = "img"
    MOV = "mov"


class Extraction(BaseModel):
    id: uuid.UUID
    type: ExtractionType = ExtractionType.TXT
    data: DataType
    metadata: dict
    document_id: uuid.UUID


class FragmentType(Enum):
    TEXT = "text"
    IMAGE = "image"


class Fragment(BaseModel):
    id: uuid.UUID
    type: FragmentType
    data: DataType
    metadata: dict
    document_id: uuid.UUID
    extraction_id: uuid.UUID
