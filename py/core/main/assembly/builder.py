import logging
from dataclasses import dataclass
from typing import Any, Optional, Type

from core.agent import R2RRAGAgent
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
from core.pipelines import KGEnrichmentPipeline, RAGPipeline, SearchPipeline
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider

from ..abstractions import R2RProviders
from ..api.v3.auth_router import AuthRouter
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
from ..app import R2RApp
from ..config import R2RConfig
from ..services.auth_service import AuthService
from ..services.ingestion_service import IngestionService
from ..services.kg_service import KgService
from ..services.management_service import ManagementService
from ..services.retrieval_service import RetrievalService
from .factory import (
    R2RAgentFactory,
    R2RPipeFactory,
    R2RPipelineFactory,
    R2RProviderFactory,
)

logger = logging.getLogger()


@dataclass
class ProviderOverrides:
    auth: Optional[AuthProvider] = None
    database: Optional[DatabaseProvider] = None
    embedding: Optional[EmbeddingProvider] = None
    llm: Optional[CompletionProvider] = None
    crypto: Optional[CryptoProvider] = None
    orchestration: Optional[OrchestrationProvider] = None


@dataclass
class PipeOverrides:
    parsing: Optional[AsyncPipe] = None
    embedding: Optional[AsyncPipe] = None
    rag: Optional[AsyncPipe] = None
    streaming_rag: Optional[AsyncPipe] = None
    vector_storage: Optional[AsyncPipe] = None
    vector_search: Optional[AsyncPipe] = None
    kg: Optional[AsyncPipe] = None
    kg_storage: Optional[AsyncPipe] = None
    kg_search: Optional[AsyncPipe] = None
    kg_entity_description: Optional[AsyncPipe] = None
    kg_clustering: Optional[AsyncPipe] = None
    kg_community_summary: Optional[AsyncPipe] = None


@dataclass
class PipelineOverrides:
    search: Optional[SearchPipeline] = None
    rag: Optional[RAGPipeline] = None
    streaming_rag: Optional[RAGPipeline] = None
    kg_enrichment: Optional[KGEnrichmentPipeline] = None


@dataclass
class ServiceOverrides:
    auth: Optional["AuthService"] = None
    ingestion: Optional["IngestionService"] = None
    management: Optional["ManagementService"] = None
    retrieval: Optional["RetrievalService"] = None
    kg: Optional["KgService"] = None


class R2RBuilder:
    def __init__(self, config: R2RConfig):
        self.config = config
        self.provider_factory_override: Optional[Type[R2RProviderFactory]] = (
            None
        )
        self.pipe_factory_override: Optional[Type[R2RPipeFactory]] = None
        self.pipeline_factory_override: Optional[Type[R2RPipelineFactory]] = (
            None
        )
        self.provider_overrides = ProviderOverrides()
        self.pipe_overrides = PipeOverrides()
        self.pipeline_overrides = PipelineOverrides()
        self.service_overrides = ServiceOverrides()
        self.assistant_factory_override: Optional[R2RAgentFactory] = None
        self.rag_agent_override: Optional[R2RRAGAgent] = None

    def with_provider_factory(self, factory: Type[R2RProviderFactory]):
        self.provider_factory_override = factory
        return self

    def with_pipe_factory(self, factory: type[R2RPipeFactory]):
        self.pipe_factory_override = factory
        return self

    def with_pipeline_factory(self, factory: type[R2RPipelineFactory]):
        self.pipeline_factory_override = factory
        return self

    def with_override(self, attr_name: str, value: Any):
        setattr(self, f"{attr_name}_override", value)
        return self

    def with_provider(self, provider_type: str, provider: Any):
        setattr(self.provider_overrides, provider_type, provider)
        return self

    def with_pipe(self, pipe_type: str, pipe: AsyncPipe):
        setattr(self.pipe_overrides, pipe_type, pipe)
        return self

    def with_pipeline(self, pipeline_type: str, pipeline: Any):
        setattr(self.pipeline_overrides, pipeline_type, pipeline)
        return self

    def with_service(self, service_type: str, service: Any):
        setattr(self.service_overrides, service_type, service)
        return self

    async def _create_providers(
        self, provider_factory: Type[R2RProviderFactory], *args, **kwargs
    ) -> Any:
        overrides = {
            k: v
            for k, v in vars(self.provider_overrides).items()
            if v is not None
        }
        kwargs = {**kwargs, **overrides}
        factory = provider_factory(self.config)
        return await factory.create_providers(*args, **kwargs)

    def _create_pipes(
        self,
        pipe_factory: type[R2RPipeFactory],
        providers: Any,
        *args,
        **kwargs,
    ) -> Any:
        overrides = {
            k: v for k, v in vars(self.pipe_overrides).items() if v is not None
        }
        return pipe_factory(self.config, providers).create_pipes(
            overrides=overrides, *args, **kwargs
        )

    def _create_pipelines(
        self,
        pipeline_factory: type[R2RPipelineFactory],
        providers: R2RProviders,
        pipes: Any,
        *args,
        **kwargs,
    ) -> Any:
        override_dict = {
            f"{k}_pipeline": v
            for k, v in vars(self.pipeline_overrides).items()
            if v is not None
        }
        kwargs.update(override_dict)
        return pipeline_factory(
            self.config, providers, pipes
        ).create_pipelines(*args, **kwargs)

    def _create_services(
        self, service_params: dict[str, Any]
    ) -> dict[str, Any]:
        services = {}
        for service_type, override in vars(self.service_overrides).items():
            logger.info(f"Creating {service_type} service")
            service_class = globals()[f"{service_type.capitalize()}Service"]
            services[service_type] = override or service_class(
                **service_params
            )
        return services

    async def build(self, *args, **kwargs) -> R2RApp:
        provider_factory = self.provider_factory_override or R2RProviderFactory
        pipe_factory = self.pipe_factory_override or R2RPipeFactory
        pipeline_factory = self.pipeline_factory_override or R2RPipelineFactory

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

        assistant_factory = self.assistant_factory_override or R2RAgentFactory(
            self.config, providers, pipelines
        )
        agents = assistant_factory.create_agents(
            overrides={"rag_agent": self.rag_agent_override}, *args, **kwargs
        )

        run_manager = RunManager(providers.logging)

        service_params = {
            "config": self.config,
            "providers": providers,
            "pipes": pipes,
            "pipelines": pipelines,
            "agents": agents,
            "run_manager": run_manager,
            "logging_connection": providers.logging,
        }

        services = self._create_services(service_params)

        orchestration_provider = providers.orchestration

        routers = {
            "auth_router": AuthRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "chunks_router": ChunksRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "collections_router": CollectionsRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "conversations_router": ConversationsRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "documents_router": DocumentsRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "graph_router": GraphRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "indices_router": IndicesRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "logs_router": LogsRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "prompts_router": PromptsRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "retrieval_router_v3": RetrievalRouterV3(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "system_router": SystemRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
            "users_router": UsersRouter(
                providers=providers,
                services=services,
                orchestration_provider=orchestration_provider,
            ).get_router(),
        }

        return R2RApp(
            config=self.config,
            orchestration_provider=orchestration_provider,
            **routers,
        )
