from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from .api.auth_router import AuthRouter
from .services.ingestion_service import IngestionService
from .api.ingestion_router import IngestionRouter
from .api.management_router import ManagementRouter
from .api.restructure_router import RestructureRouter
from .api.retrieval_router import RetrievalRouter
from .config import R2RConfig

from .hatchet import IngestionWorkflow, r2r_hatchet


class R2RApp:
    def __init__(
        self,
        config: R2RConfig,
        auth_router: AuthRouter,
        ingestion_service: IngestionService,
        ingestion_router: IngestionRouter,
        management_router: ManagementRouter,
        retrieval_router: RestructureRouter,
        restructure_router: RetrievalRouter,
    ):
        self.config = config
        self.ingestion_service = ingestion_service
        self.ingestion_router = ingestion_router
        self.management_router = management_router
        self.retrieval_router = retrieval_router
        self.auth_router = auth_router
        self.restructure_router = restructure_router
        self.app = FastAPI()
        self._setup_routes()
        self._setup_hatchet_worker()
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

    def _setup_hatchet_worker(
        self,
    ):
        self.r2r_worker = r2r_hatchet.worker("r2r-worker")

        ingestion_workflow = IngestionWorkflow(self.ingestion_service)
        self.r2r_worker.register_workflow(ingestion_workflow)

    def _apply_cors(self):
        origins = ["*", "http://localhost:3000", "http://localhost:8000"]
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def serve(
        self, host: str = "0.0.0.0", port: int = 8000, max_threads: int = 1
    ):
        import uvicorn
        import asyncio

        # Start the Hatchet worker in a separate thread
        import threading

        r2r_worker_thread = threading.Thread(
            target=self.r2r_worker.start, daemon=True
        )
        r2r_worker_thread.start()

        # Run the FastAPI app
        uvicorn.run(self.app, host=host, port=port)
