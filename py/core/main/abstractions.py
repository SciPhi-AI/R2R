from pydantic import BaseModel

from core.agent import R2RRAGAgent, R2RStreamingRAGAgent
from core.base.pipes import AsyncPipe
from core.base.providers import (
    AuthProvider,
    CompletionProvider,
    DatabaseProvider,
    EmbeddingProvider,
    FileProvider,
    IngestionProvider,
    KGProvider,
    OrchestrationProvider,
    PromptProvider,
)
from core.pipelines import RAGPipeline, SearchPipeline


class R2RProviders(BaseModel):
    auth: AuthProvider
    database: DatabaseProvider
    ingestion: IngestionProvider
    embedding: EmbeddingProvider
    file: FileProvider
    kg: KGProvider
    llm: CompletionProvider
    orchestration: OrchestrationProvider
    prompt: PromptProvider

    class Config:
        arbitrary_types_allowed = True


class R2RPipes(BaseModel):
    parsing_pipe: AsyncPipe
    embedding_pipe: AsyncPipe
    kg_search_pipe: AsyncPipe
    kg_triples_extraction_pipe: AsyncPipe
    kg_storage_pipe: AsyncPipe
    kg_entity_description_pipe: AsyncPipe
    kg_clustering_pipe: AsyncPipe
    kg_community_summary_pipe: AsyncPipe
    rag_pipe: AsyncPipe
    streaming_rag_pipe: AsyncPipe
    vector_storage_pipe: AsyncPipe
    vector_search_pipe: AsyncPipe

    class Config:
        arbitrary_types_allowed = True


class R2RPipelines(BaseModel):
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
