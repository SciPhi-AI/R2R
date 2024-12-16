from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

from core.agent import R2RRAGAgent, R2RStreamingRAGAgent
from core.base.pipes import AsyncPipe
from core.database import PostgresDatabaseProvider
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
    R2RAuthProvider,
    R2RIngestionProvider,
    SendGridEmailProvider,
    SimpleOrchestrationProvider,
    SupabaseAuthProvider,
    UnstructuredIngestionProvider,
)

if TYPE_CHECKING:
    from core.main.services.auth_service import AuthService
    from core.main.services.ingestion_service import IngestionService
    from core.main.services.kg_service import KgService
    from core.main.services.management_service import ManagementService
    from core.main.services.retrieval_service import RetrievalService


class R2RProviders(BaseModel):
    auth: R2RAuthProvider | SupabaseAuthProvider
    database: PostgresDatabaseProvider
    ingestion: R2RIngestionProvider | UnstructuredIngestionProvider
    embedding: (
        LiteLLMEmbeddingProvider
        | OpenAIEmbeddingProvider
        | OllamaEmbeddingProvider
    )
    llm: LiteLLMCompletionProvider | OpenAICompletionProvider
    orchestration: HatchetOrchestrationProvider | SimpleOrchestrationProvider
    email: (
        AsyncSMTPEmailProvider
        | ConsoleMockEmailProvider
        | SendGridEmailProvider
    )

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


@dataclass
class R2RServices:
    auth: Optional["AuthService"] = None
    ingestion: Optional["IngestionService"] = None
    management: Optional["ManagementService"] = None
    retrieval: Optional["RetrievalService"] = None
    kg: Optional["KgService"] = None
