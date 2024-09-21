from pydantic import BaseModel

from core.agent import R2RRAGAgent, R2RStreamingRAGAgent
from core.base.pipes import AsyncPipe
from core.base.providers import (
    AuthProvider,
    ChunkingProvider,
    CompletionProvider,
    DatabaseProvider,
    EmbeddingProvider,
    FileProvider,
    KGProvider,
    OrchestrationProvider,
    ParsingProvider,
    PromptProvider,
)
from core.pipelines import RAGPipeline, SearchPipeline


class R2RProviders(BaseModel):
    auth: AuthProvider
    chunking: ChunkingProvider
    database: DatabaseProvider
    kg: KGProvider
    llm: CompletionProvider
    embedding: EmbeddingProvider
    orchestration: OrchestrationProvider
    prompt: PromptProvider
    parsing: ParsingProvider
    file: FileProvider

    class Config:
        arbitrary_types_allowed = True


class R2RPipes(BaseModel):
    parsing_pipe: AsyncPipe
    chunking_pipe: AsyncPipe
    embedding_pipe: AsyncPipe
    vector_storage_pipe: AsyncPipe
    vector_search_pipe: AsyncPipe
    rag_pipe: AsyncPipe
    streaming_rag_pipe: AsyncPipe
    kg_search_pipe: AsyncPipe
    kg_extraction_pipe: AsyncPipe
    kg_storage_pipe: AsyncPipe
    kg_node_extraction_pipe: AsyncPipe
    kg_node_description_pipe: AsyncPipe
    kg_clustering_pipe: AsyncPipe
    kg_community_summary_pipe: AsyncPipe

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
