from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from core.base.providers import OrchestrationProvider

from .api.auth_router import AuthRouter
from .api.ingestion_router import IngestionRouter
from .api.management_router import ManagementRouter
from .api.restructure_router import RestructureRouter
from .api.retrieval_router import RetrievalRouter
from .config import R2RConfig
from .services.ingestion_service import IngestionService
from .services.restructure_service import RestructureService


class R2RApp:
    def __init__(
        self,
        config: R2RConfig,
        orchestration_provider: OrchestrationProvider,
        auth_router: AuthRouter,
        ingestion_router: IngestionRouter,
        management_router: ManagementRouter,
        retrieval_router: RestructureRouter,
        restructure_router: RetrievalRouter,
    ):
        self.config = config
        self.ingestion_router = ingestion_router
        self.management_router = management_router
        self.retrieval_router = retrieval_router
        self.auth_router = auth_router
        self.restructure_router = restructure_router
        self.orchestration_provider = orchestration_provider
        self.app = FastAPI()
        self._setup_routes()
        self._apply_cors()

    def _setup_routes(self):

        # Include routers in the app
        self.app.include_router(self.ingestion_router, prefix="/v2")
        self.app.include_router(self.management_router, prefix="/v2")
        self.app.include_router(self.retrieval_router, prefix="/v2")
        self.app.include_router(self.auth_router, prefix="/v2")
        self.app.include_router(self.restructure_router, prefix="/v2")

        @self.app.get("/v2/openapi_spec")
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

    def serve(self, host: str = "0.0.0.0", port: int = 7272):
        # Start the Hatchet worker in a separate thread
        import uvicorn

        # Run the FastAPI app
        uvicorn.run(self.app, host=host, port=port)
