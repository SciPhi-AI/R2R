from pydantic import BaseModel

from r2r.core import (
    EmbeddingProvider,
    EvalPipeline,
    EvalProvider,
    IngestionPipeline,
    LLMProvider,
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


class R2RPipelines(BaseModel):
    eval_pipeline: EvalPipeline
    ingestion_pipeline: IngestionPipeline
    search_pipeline: SearchPipeline
    rag_pipeline: RAGPipeline
    streaming_rag_pipeline: RAGPipeline

    class Config:
        arbitrary_types_allowed = True
