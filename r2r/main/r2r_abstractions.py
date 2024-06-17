from typing import Optional

from pydantic import BaseModel

from r2r.core import (
    EmbeddingProvider,
    EvalPipeline,
    EvalProvider,
    IngestionPipeline,
    KGProvider,
    LLMProvider,
    LoggableAsyncPipe,
    PromptProvider,
    RAGPipeline,
    SearchPipeline,
    VectorDBProvider,
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
