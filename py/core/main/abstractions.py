from typing import Union

from pydantic import BaseModel

from core.agent import R2RRAGAgent, R2RStreamingRAGAgent
from core.base.pipes import AsyncPipe
from core.pipelines import RAGPipeline, SearchPipeline
from core.providers import (
    AsyncSMTPEmailProvider,
    ConsoleMockEmailProvider,
    HatchetOrchestrationProvider,
    LiteLLMCompletionProvider,
    LiteLLMEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAICompletionProvider,
    OpenAIEmbeddingProvider,
    PostgresDBProvider,
    R2RAuthProvider,
    R2RIngestionProvider,
    SendGridEmailProvider,
    SimpleOrchestrationProvider,
    SqlitePersistentLoggingProvider,
    SupabaseAuthProvider,
    UnstructuredIngestionProvider,
)


class R2RProviders(BaseModel):
    auth: Union[R2RAuthProvider, SupabaseAuthProvider]
    database: PostgresDBProvider
    ingestion: Union[R2RIngestionProvider, UnstructuredIngestionProvider]
    embedding: Union[
        LiteLLMEmbeddingProvider,
        OpenAIEmbeddingProvider,
        OllamaEmbeddingProvider,
    ]
    llm: Union[LiteLLMCompletionProvider, OpenAICompletionProvider]
    orchestration: Union[
        HatchetOrchestrationProvider, SimpleOrchestrationProvider
    ]
    logging: SqlitePersistentLoggingProvider
    email: Union[
        AsyncSMTPEmailProvider, ConsoleMockEmailProvider, SendGridEmailProvider
    ]

    class Config:
        arbitrary_types_allowed = True


class R2RPipes(BaseModel):
    parsing_pipe: AsyncPipe
    embedding_pipe: AsyncPipe
    kg_search_pipe: AsyncPipe
    kg_relationships_extraction_pipe: AsyncPipe
    kg_storage_pipe: AsyncPipe
    kg_entity_description_pipe: AsyncPipe
    kg_clustering_pipe: AsyncPipe
    kg_entity_deduplication_pipe: AsyncPipe
    kg_entity_deduplication_summary_pipe: AsyncPipe
    kg_community_summary_pipe: AsyncPipe
    kg_prompt_tuning_pipe: AsyncPipe
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
