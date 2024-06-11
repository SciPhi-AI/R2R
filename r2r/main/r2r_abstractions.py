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
    parsing_pipe: LoggableAsyncPipe
    embedding_pipe: LoggableAsyncPipe
    vector_storage_pipe: LoggableAsyncPipe
    search_pipe: LoggableAsyncPipe
    rag_pipe: LoggableAsyncPipe
    streaming_rag_pipe: LoggableAsyncPipe
    eval_pipe: LoggableAsyncPipe
    kg_pipe: LoggableAsyncPipe
    kg_storage_pipe: LoggableAsyncPipe

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
