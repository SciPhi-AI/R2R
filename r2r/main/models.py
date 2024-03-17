from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from r2r.core import BasicDocument


class EmbeddingsSettingsModel(BaseModel):
    do_chunking: Optional[bool] = True
    do_upsert: Optional[bool] = True


class IngestionSettingsModel(BaseModel):
    pass


class RAGSettingsModel(BaseModel):
    pass


class SettingsModel(BaseModel):
    embedding_settings: EmbeddingsSettingsModel = EmbeddingsSettingsModel()
    ingestion_settings: IngestionSettingsModel = IngestionSettingsModel()
    rag_settings: RAGSettingsModel = RAGSettingsModel()


class EntryModel(BaseModel):
    document_id: str
    blobs: dict[str, str]
    metadata: Optional[dict]


class EvalPayloadModel(BaseModel):
    query: str
    context: str
    completion_text: str
    run_id: str
    settings: RAGSettingsModel


# File upload class, to be fixed later
# class FileUploadRequest(BaseModel):
# document_id: str
# metadata: Optional[dict]
# settings: SettingsModel = SettingsModel()


class AddEntryRequest(BaseModel):
    entry: EntryModel
    settings: SettingsModel = SettingsModel()


class AddEntriesRequest(BaseModel):
    entries: list[EntryModel]
    settings: SettingsModel = SettingsModel()


class GenerationConfigModel(BaseModel):
    temperature: float = 0.1
    top_p: float = 1.0
    top_k: int = 100
    max_tokens_to_sample: int = 1_024
    model: Optional[str] = "gpt-4-0125-preview"
    stream: bool = False
    functions: Optional[list[dict]] = None
    skip_special_tokens: bool = False
    stop_token: Optional[str] = None
    num_beams: int = 1
    do_sample: bool = True
    add_generation_kwargs: dict = {}
    generate_with_chat: bool = False


class RAGQueryModel(BaseModel):
    query: str
    limit: Optional[int] = 10
    filters: dict = {}
    settings: SettingsModel = SettingsModel()
    generation_config: GenerationConfigModel = GenerationConfigModel()


def to_camel(string: str) -> str:
    return "".join(
        word.capitalize() if i != 0 else word
        for i, word in enumerate(string.split("_"))
    )


class LogModel(BaseModel):
    timestamp: datetime = Field(alias="timestamp")
    pipeline_run_id: str = Field(alias="pipelineRunId")
    pipeline_run_type: str = Field(alias="pipelineRunType")
    method: str = Field(alias="method")
    result: str = Field(alias="result")
    log_level: str = Field(alias="logLevel")

    class Config:
        alias_generator = to_camel
        populate_by_name = True


# TODO - Split apart `retrieval` and `embedding` event logs
class SummaryLogModel(BaseModel):
    timestamp: datetime = Field(alias="timestamp")
    pipeline_run_id: str = Field(alias="pipelineRunId")
    pipeline_run_type: str = Field(alias="pipelineRunType")
    method: str = Field(alias="method")
    embedding_chunks: Optional[str] = Field(alias="embeddingChunks")
    search_query: str = Field(alias="searchQuery")
    search_results: list[dict] = Field(alias="searchResults")
    completion_result: str = Field(alias="completionResult")
    eval_results: Optional[dict] = Field(alias="evalResults")
    document: Optional[BasicDocument] = Field(alias="document")
    outcome: str = Field(alias="outcome")

    class Config:
        alias_generator = to_camel
        populate_by_name = True
