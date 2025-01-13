from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from core.agent import FUSERAGAgent, FUSEStreamingRAGAgent
from core.database import PostgresDatabaseProvider
from core.pipelines import RAGPipeline, SearchPipeline
from core.pipes import (
    EmbeddingPipe,
    GraphClusteringPipe,
    GraphCommunitySummaryPipe,
    GraphDescriptionPipe,
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
    FUSEAuthProvider,
    FUSEIngestionProvider,
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


class FUSEProviders(BaseModel):
    auth: FUSEAuthProvider | SupabaseAuthProvider
    database: PostgresDatabaseProvider
    ingestion: FUSEIngestionProvider | UnstructuredIngestionProvider
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


class FUSEPipes(BaseModel):
    parsing_pipe: ParsingPipe
    embedding_pipe: EmbeddingPipe
    graph_search_pipe: GraphSearchSearchPipe
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


class FUSEPipelines(BaseModel):
    search_pipeline: SearchPipeline
    rag_pipeline: RAGPipeline
    streaming_rag_pipeline: RAGPipeline

    class Config:
        arbitrary_types_allowed = True


class FUSEAgents(BaseModel):
    rag_agent: FUSERAGAgent
    streaming_rag_agent: FUSEStreamingRAGAgent

    class Config:
        arbitrary_types_allowed = True


@dataclass
class FUSEServices:
    auth: "AuthService"
    ingestion: "IngestionService"
    management: "ManagementService"
    retrieval: "RetrievalService"
    graph: "GraphService"
