from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

from core.providers import (
    AsyncSMTPEmailProvider,
    ConsoleMockEmailProvider,
    HatchetOrchestrationProvider,
    JwtAuthProvider,
    PostgresDatabaseProvider,
    R2RAuthProvider,
    R2RIngestionProvider,
    SendGridEmailProvider,
    SimpleOrchestrationProvider,
    SupabaseAuthProvider,
    UnstructuredIngestionProvider,
)
from core.base.providers.embedding import EmbeddingProvider
from core.base.providers.llm import CompletionProvider

if TYPE_CHECKING:
    from core.main.services.auth_service import AuthService
    from core.main.services.graph_service import GraphService
    from core.main.services.ingestion_service import IngestionService
    from core.main.services.management_service import ManagementService
    from core.main.services.retrieval_service import RetrievalService


class R2RProviders(BaseModel):
    auth: R2RAuthProvider | SupabaseAuthProvider | JwtAuthProvider
    database: PostgresDatabaseProvider
    ingestion: R2RIngestionProvider | UnstructuredIngestionProvider
    embedding: EmbeddingProvider
    completion_embedding: EmbeddingProvider
    llm: CompletionProvider
    orchestration: HatchetOrchestrationProvider | SimpleOrchestrationProvider
    email: (
        AsyncSMTPEmailProvider
        | ConsoleMockEmailProvider
        | SendGridEmailProvider
    )

    class Config:
        arbitrary_types_allowed = True


@dataclass
class R2RServices:
    auth: "AuthService"
    ingestion: "IngestionService"
    management: "ManagementService"
    retrieval: "RetrievalService"
    graph: "GraphService"
