from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

from core.providers import (
    AnthropicCompletionProvider,
    APSchedulerProvider,
    AsyncSMTPEmailProvider,
    ClerkAuthProvider,
    ConsoleMockEmailProvider,
    HatchetOrchestrationProvider,
    JwtAuthProvider,
    LiteLLMCompletionProvider,
    LiteLLMEmbeddingProvider,
    MailerSendEmailProvider,
    OllamaEmbeddingProvider,
    OpenAICompletionProvider,
    OpenAIEmbeddingProvider,
    PostgresDatabaseProvider,
    R2RAuthProvider,
    R2RCompletionProvider,
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
    from core.main.services.maintenance_service import MaintenanceService
    from core.main.services.management_service import ManagementService
    from core.main.services.retrieval_service import (  # type: ignore
        RetrievalService,  # type: ignore
    )


class R2RProviders(BaseModel):
    auth: (
        R2RAuthProvider
        | SupabaseAuthProvider
        | JwtAuthProvider
        | ClerkAuthProvider
    )
    database: PostgresDatabaseProvider
    ingestion: R2RIngestionProvider | UnstructuredIngestionProvider
    email: (
        AsyncSMTPEmailProvider
        | ConsoleMockEmailProvider
        | SendGridEmailProvider
        | MailerSendEmailProvider
    )
    embedding: (
        LiteLLMEmbeddingProvider
        | OpenAIEmbeddingProvider
        | OllamaEmbeddingProvider
    )
    completion_embedding: (
        LiteLLMEmbeddingProvider
        | OpenAIEmbeddingProvider
        | OllamaEmbeddingProvider
    )
    llm: (
        AnthropicCompletionProvider
        | LiteLLMCompletionProvider
        | OpenAICompletionProvider
        | R2RCompletionProvider
    )
    orchestration: HatchetOrchestrationProvider | SimpleOrchestrationProvider
    scheduler: APSchedulerProvider

    class Config:
        arbitrary_types_allowed = True


@dataclass
class R2RServices:
    auth: "AuthService"
    ingestion: "IngestionService"
    maintenance: "MaintenanceService"
    management: "ManagementService"
    retrieval: "RetrievalService"
    graph: "GraphService"
