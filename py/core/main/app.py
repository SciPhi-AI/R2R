from typing import Union

from core.base import R2RException
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from .api.auth_router import AuthRouter
from .api.ingestion_router import IngestionRouter
from .api.kg_router import KGRouter
from .api.management_router import ManagementRouter
from .api.retrieval_router import RetrievalRouter
from .config import R2RConfig


class R2RApp:
    def __init__(
        self,
        config: R2RConfig,
        orchestration_provider: Union[
            HatchetOrchestrationProvider, SimpleOrchestrationProvider
        ],
        auth_router: AuthRouter,
        ingestion_router: IngestionRouter,
        management_router: ManagementRouter,
        retrieval_router: RetrievalRouter,
        kg_router: KGRouter,
    ):
        self.config = config
        self.ingestion_router = ingestion_router
        self.management_router = management_router
        self.retrieval_router = retrieval_router
        self.auth_router = auth_router
        self.kg_router = kg_router
        self.orchestration_provider = orchestration_provider
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
        # Include routers in the app
        self.app.include_router(self.ingestion_router, prefix="/v2")
        self.app.include_router(self.management_router, prefix="/v2")
        self.app.include_router(self.retrieval_router, prefix="/v2")
        self.app.include_router(self.auth_router, prefix="/v2")
        self.app.include_router(self.kg_router, prefix="/v2")

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

    async def serve(self, host: str = "0.0.0.0", port: int = 7272):
        # Start the Hatchet worker in a separate thread
        import uvicorn

        # Run the FastAPI app
        config = uvicorn.Config(self.app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()
