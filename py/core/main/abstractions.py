from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from core.agent import R2RRAGAgent, R2RStreamingRAGAgent
from core.database import PostgresDatabaseProvider
from core.pipelines import RAGPipeline, SearchPipeline
from core.pipes import (
    EmbeddingPipe,
    GraphClusteringPipe,
    GraphCommunitySummaryPipe,
    GraphDescriptionPipe,
    GraphExtractionPipe,
    GraphSearchSearchPipe,
    GraphStoragePipe,
    ParsingPipe,
    RAGPipe,
    SearchPipe,
    StreamingRAGPipe,
    VectorStoragePipe,
)
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
    from core.main.services.graph_service import GraphService
    from core.main.services.ingestion_service import IngestionService
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
    parsing_pipe: ParsingPipe
    embedding_pipe: EmbeddingPipe
    graph_search_pipe: GraphSearchSearchPipe
    graph_extraction_pipe: GraphExtractionPipe
    graph_storage_pipe: GraphStoragePipe
    graph_description_pipe: GraphDescriptionPipe
    graph_clustering_pipe: GraphClusteringPipe
    graph_community_summary_pipe: GraphCommunitySummaryPipe
    rag_pipe: RAGPipe
    streaming_rag_pipe: StreamingRAGPipe
    vector_storage_pipe: VectorStoragePipe
    vector_search_pipe: Any  # TODO - Fix

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
    auth: "AuthService"
    ingestion: "IngestionService"
    management: "ManagementService"
    retrieval: "RetrievalService"
    graph: "GraphService"
