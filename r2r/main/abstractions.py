from typing import Optional

from pydantic import BaseModel

from r2r.agents import R2RRAGAgent, R2RStreamingRAGAgent
from r2r.base import (
    AsyncPipe,
    AuthProvider,
    ChunkingProvider,
    CompletionProvider,
    DatabaseProvider,
    EmbeddingProvider,
    EvalProvider,
    KGProvider,
    ParsingProvider,
    PromptProvider,
)
from r2r.pipelines import (
    EvalPipeline,
    IngestionPipeline,
    RAGPipeline,
    SearchPipeline,
)


class R2RProviders(BaseModel):
    auth: Optional[AuthProvider]
    chunking: Optional[ChunkingProvider]
    llm: Optional[CompletionProvider]
    database: Optional[DatabaseProvider]
    embedding: Optional[EmbeddingProvider]
    prompt: Optional[PromptProvider]
    eval: Optional[EvalProvider]
    kg: Optional[KGProvider]
    parsing: Optional[ParsingProvider]

    class Config:
        arbitrary_types_allowed = True


class R2RPipes(BaseModel):
    parsing_pipe: Optional[AsyncPipe]
    chunking_pipe: Optional[AsyncPipe]
    embedding_pipe: Optional[AsyncPipe]
    vector_storage_pipe: Optional[AsyncPipe]
    vector_search_pipe: Optional[AsyncPipe]
    rag_pipe: Optional[AsyncPipe]
    streaming_rag_pipe: Optional[AsyncPipe]
    eval_pipe: Optional[AsyncPipe]
    kg_pipe: Optional[AsyncPipe]
    kg_storage_pipe: Optional[AsyncPipe]
    kg_search_search_pipe: Optional[AsyncPipe]

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


class R2RAgents(BaseModel):
    rag_agent: R2RRAGAgent
    streaming_rag_agent: R2RStreamingRAGAgent

    class Config:
        arbitrary_types_allowed = True
