from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from core.base import R2RException
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from core.utils.sentry import init_sentry

from .abstractions import R2RServices
from .api.v3.chunks_router import ChunksRouter
from .api.v3.collections_router import CollectionsRouter
from .api.v3.conversations_router import ConversationsRouter
from .api.v3.documents_router import DocumentsRouter
from .api.v3.graph_router import GraphRouter
from .api.v3.indices_router import IndicesRouter
from .api.v3.prompts_router import PromptsRouter
from .api.v3.retrieval_router import RetrievalRouter
from .api.v3.system_router import SystemRouter
from .api.v3.users_router import UsersRouter
from .config import R2RConfig


class R2RApp:
    def __init__(
        self,
        config: R2RConfig,
        orchestration_provider: (
            HatchetOrchestrationProvider | SimpleOrchestrationProvider
        ),
        services: R2RServices,
        chunks_router: ChunksRouter,
        collections_router: CollectionsRouter,
        conversations_router: ConversationsRouter,
        documents_router: DocumentsRouter,
        graph_router: GraphRouter,
        indices_router: IndicesRouter,
        prompts_router: PromptsRouter,
        retrieval_router: RetrievalRouter,
        system_router: SystemRouter,
        users_router: UsersRouter,
    ):
        init_sentry()

        self.config = config
        self.services = services
        self.chunks_router = chunks_router
        self.collections_router = collections_router
        self.conversations_router = conversations_router
        self.documents_router = documents_router
        self.graph_router = graph_router
        self.indices_router = indices_router
        self.orchestration_provider = orchestration_provider
        self.prompts_router = prompts_router
        self.retrieval_router = retrieval_router
        self.system_router = system_router
        self.users_router = users_router

        self.app = FastAPI()

        @self.app.exception_handler(R2RException)
        async def r2r_exception_handler(request: Request, exc: R2RException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "message": exc.message,
                    "error_type": type(exc).__name__,
                },
            )

        self._setup_routes()
        self._apply_cors()

    def _setup_routes(self):
        self.app.include_router(self.chunks_router, prefix="/v3")
        self.app.include_router(self.collections_router, prefix="/v3")
        self.app.include_router(self.conversations_router, prefix="/v3")
        self.app.include_router(self.documents_router, prefix="/v3")
        self.app.include_router(self.graph_router, prefix="/v3")
        self.app.include_router(self.indices_router, prefix="/v3")
        self.app.include_router(self.prompts_router, prefix="/v3")
        self.app.include_router(self.retrieval_router, prefix="/v3")
        self.app.include_router(self.system_router, prefix="/v3")
        self.app.include_router(self.users_router, prefix="/v3")

        @self.app.get("/openapi_spec", include_in_schema=False)
        async def openapi_spec():
            return get_openapi(
                title="R2R Application API",
                version="1.0.0",
                routes=self.app.routes,
            )

    def _apply_cors(self):
        origins = ["*", "http://localhost:3000", "http://localhost:7272"]
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    async def serve(self, host: str = "0.0.0.0", port: int = 7272):
        import uvicorn

        from core.utils.logging_config import configure_logging

        configure_logging()

        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_config=None,
        )
        server = uvicorn.Server(config)
        await server.serve()
