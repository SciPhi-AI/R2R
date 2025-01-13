import logging
from typing import Any, Type

from core.agent import FUSERAGAgent
from core.base import (
    AsyncPipe,
    AuthProvider,
    CompletionProvider,
    CryptoProvider,
    DatabaseProvider,
    EmbeddingProvider,
    OrchestrationProvider,
    RunManager,
)
from core.main.abstractions import FUSEServices
from core.main.services.auth_service import AuthService
from core.main.services.graph_service import GraphService
from core.main.services.ingestion_service import IngestionService
from core.main.services.management_service import ManagementService
from core.main.services.retrieval_service import RetrievalService
from core.pipelines import KGEnrichmentPipeline, RAGPipeline, SearchPipeline

from ..abstractions import FUSEProviders
from ..api.v3.chunks_router import ChunksRouter
from ..api.v3.collections_router import CollectionsRouter
from ..api.v3.conversations_router import ConversationsRouter
from ..api.v3.documents_router import DocumentsRouter
from ..api.v3.graph_router import GraphRouter
from ..api.v3.indices_router import IndicesRouter
from ..api.v3.logs_router import LogsRouter
from ..api.v3.prompts_router import PromptsRouter
from ..api.v3.retrieval_router import RetrievalRouterV3
from ..api.v3.system_router import SystemRouter
from ..api.v3.users_router import UsersRouter
from ..app import FUSEApp
from ..config import FUSEConfig
from .factory import (
    FUSEAgentFactory,
    FUSEPipeFactory,
    FUSEPipelineFactory,
    FUSEProviderFactory,
)

logger = logging.getLogger()


class FUSEBuilder:
    def __init__(self, config: FUSEConfig):
        self.config = config

    def _create_pipes(
        self,
        pipe_factory: type[FUSEPipeFactory],
        providers: FUSEProviders,
        *args,
        **kwargs,
    ) -> Any:
        return pipe_factory(self.config, providers).create_pipes(
            overrides={}, *args, **kwargs
        )

    def _create_pipelines(
        self,
        pipeline_factory: type[FUSEPipelineFactory],
        providers: FUSEProviders,
        pipes: Any,
        *args,
        **kwargs,
    ) -> Any:
        return pipeline_factory(
            self.config, providers, pipes
        ).create_pipelines(*args, **kwargs)

    def _create_services(self, service_params: dict[str, Any]) -> FUSEServices:
        services = ["auth", "ingestion", "management", "retrieval", "graph"]
        service_instances = {}

        for service_type in services:
            service_class = globals()[f"{service_type.capitalize()}Service"]
            service_instances[service_type] = service_class(**service_params)

        return FUSEServices(**service_instances)

    async def _create_providers(
        self, provider_factory: Type[FUSEProviderFactory], *args, **kwargs
    ) -> Any:
        factory = provider_factory(self.config)
        return await factory.create_providers(*args, **kwargs)

    async def build(self, *args, **kwargs) -> FUSEApp:
        provider_factory = FUSEProviderFactory
        pipe_factory = FUSEPipeFactory
        pipeline_factory = FUSEPipelineFactory

        try:
            providers = await self._create_providers(
                provider_factory, *args, **kwargs
            )
            pipes = self._create_pipes(
                pipe_factory, providers, *args, **kwargs
            )
            pipelines = self._create_pipelines(
                pipeline_factory, providers, pipes, *args, **kwargs
            )
        except Exception as e:
            logger.error(f"Error creating providers, pipes, or pipelines: {e}")
            raise

        assistant_factory = FUSEAgentFactory(self.config, providers, pipelines)
        agents = assistant_factory.create_agents(*args, **kwargs)

        run_manager = RunManager()

        service_params = {
            "config": self.config,
            "providers": providers,
            "pipes": pipes,
            "pipelines": pipelines,
            "agents": agents,
            "run_manager": run_manager,
        }

        services = self._create_services(service_params)

        routers = {
            "chunks_router": ChunksRouter(
                providers=providers,
                services=services,
            ).get_router(),
            "collections_router": CollectionsRouter(
                providers=providers,
                services=services,
            ).get_router(),
            "conversations_router": ConversationsRouter(
                providers=providers,
                services=services,
            ).get_router(),
            "documents_router": DocumentsRouter(
                providers=providers,
                services=services,
            ).get_router(),
            "graph_router": GraphRouter(
                providers=providers,
                services=services,
            ).get_router(),
            "indices_router": IndicesRouter(
                providers=providers,
                services=services,
            ).get_router(),
            "logs_router": LogsRouter(
                providers=providers,
                services=services,
            ).get_router(),
            "prompts_router": PromptsRouter(
                providers=providers,
                services=services,
            ).get_router(),
            "retrieval_router_v3": RetrievalRouterV3(
                providers=providers,
                services=services,
            ).get_router(),
            "system_router": SystemRouter(
                providers=providers,
                services=services,
            ).get_router(),
            "users_router": UsersRouter(
                providers=providers,
                services=services,
            ).get_router(),
        }

        return FUSEApp(
            config=self.config,
            orchestration_provider=providers.orchestration,
            **routers,
        )
