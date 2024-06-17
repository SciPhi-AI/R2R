from typing import Optional, Union

from pydantic import BaseModel

from r2r.core import (
    Document,
    EmbeddingProvider,
    EvalPipeline,
    EvalProvider,
    IngestionPipeline,
    KGProvider,
    KGSearchSettings,
    LLMProvider,
    LoggableAsyncPipe,
    PromptProvider,
    RAGPipeline,
    SearchPipeline,
    VectorDBProvider,
    VectorSearchSettings,
)


class R2RProviders(BaseModel):
    vector_db: Optional[VectorDBProvider]
    embedding: Optional[EmbeddingProvider]
    llm: Optional[LLMProvider]
    prompt: Optional[PromptProvider]
    eval: Optional[EvalProvider]
    kg: Optional[KGProvider]

    class Config:
        arbitrary_types_allowed = True


class R2RPipes(BaseModel):
    parsing_pipe: Optional[LoggableAsyncPipe]
    embedding_pipe: Optional[LoggableAsyncPipe]
    vector_storage_pipe: Optional[LoggableAsyncPipe]
    vector_search_pipe: Optional[LoggableAsyncPipe]
    rag_pipe: Optional[LoggableAsyncPipe]
    streaming_rag_pipe: Optional[LoggableAsyncPipe]
    eval_pipe: Optional[LoggableAsyncPipe]
    kg_pipe: Optional[LoggableAsyncPipe]
    kg_storage_pipe: Optional[LoggableAsyncPipe]
    kg_agent_search_pipe: Optional[LoggableAsyncPipe]

    class Config:
        arbitrary_types_allowed = True


class R2RPipelines(BaseModel):
    eval_pipeline: EvalPipeline
    ingestion_pipeline: IngestionPipeline
    search_pipeline: SearchPipeline
    rag_pipeline: RAGPipeline
    streaming_rag_pipeline: RAGPipeline

    class Config:
        arbitrary_types_allowed = True


class UpdatePromptRequest(BaseModel):
    name: str
    template: Optional[str] = None
    input_types: Optional[dict[str, str]] = None


class IngestDocumentsRequest(BaseModel):
    documents: list[Document]


class UpdateDocumentsRequest(BaseModel):
    documents: list[Document]


class SearchRequest(BaseModel):
    query: str
    vector_settings: VectorSearchSettings
    kg_settings: KGSearchSettings


class RAGRequest(BaseModel):
    message: str
    search_filters: Optional[str] = None
    search_limit: int = 10
    rag_generation_config: Optional[str] = None
    streaming: Optional[bool] = None


class EvalRequest(BaseModel):
    query: str
    context: str
    completion: str


class DeleteRequest(BaseModel):
    keys: list[str]
    values: list[Union[bool, int, str]]
