from pydantic import BaseModel

from r2r.core import (
    EmbeddingProvider,
    EvalPipeline,
    EvalProvider,
    IngestionPipeline,
    LLMProvider,
    LoggableAsyncPipe,
    PromptProvider,
    RAGPipeline,
    SearchPipeline,
    VectorDBProvider,
)


class R2RProviders(BaseModel):
    vector_db: VectorDBProvider
    embedding: EmbeddingProvider
    llm: LLMProvider
    prompt: PromptProvider
    eval: EvalProvider

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
