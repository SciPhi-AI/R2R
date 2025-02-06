import logging
from typing import Any, Type

from ..abstractions import R2RProviders, R2RServices
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
from ..services.graph_service import GraphService
from ..services.ingestion_service import IngestionService
from ..services.management_service import ManagementService
from ..services.retrieval_service import RetrievalService
from .factory import R2RProviderFactory

logger = logging.getLogger()


class R2RBuilder:
    _SERVICES = ["auth", "ingestion", "management", "retrieval", "graph"]

    def __init__(self, config: R2RConfig):
        self.config = config

    async def build(self, *args, **kwargs) -> R2RApp:
        provider_factory = R2RProviderFactory

        try:
            providers = await self._create_providers(
                provider_factory, *args, **kwargs
            )
        except Exception as e:
            logger.error(f"Error {e} while creating R2RProviders.")
            raise

        service_params = {
            "config": self.config,
            "providers": providers,
        }

        services = self._create_services(service_params)

        routers = {
            "chunks_router": ChunksRouter(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
            "collections_router": CollectionsRouter(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
            "conversations_router": ConversationsRouter(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
            "documents_router": DocumentsRouter(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
            "graph_router": GraphRouter(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
            "indices_router": IndicesRouter(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
            "logs_router": LogsRouter(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
            "prompts_router": PromptsRouter(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
            "retrieval_router_v3": RetrievalRouterV3(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
            "system_router": SystemRouter(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
            "users_router": UsersRouter(
                providers=providers,
                services=services,
                config=self.config,
            ).get_router(),
        }

        return R2RApp(
            config=self.config,
            orchestration_provider=providers.orchestration,
            services=services,
            **routers,
        )

    async def _create_providers(
        self, provider_factory: Type[R2RProviderFactory], *args, **kwargs
    ) -> R2RProviders:
        factory = provider_factory(self.config)
        return await factory.create_providers(*args, **kwargs)

    def _create_services(self, service_params: dict[str, Any]) -> R2RServices:
        services = R2RBuilder._SERVICES
        service_instances = {}

        for service_type in services:
            service_class = globals()[f"{service_type.capitalize()}Service"]
            service_instances[service_type] = service_class(**service_params)

        return R2RServices(**service_instances)
