from typing import Optional

from fastapi import FastAPI

from r2r.core import AsyncSyncMeta, KVLoggingSingleton, RunManager, syncable

from .abstractions import R2RPipelines, R2RProviders
from .assembly.config import R2RConfig
from .services.ingestion_service import IngestionService
from .services.retrieval_service import RetrievalService


class R2RApp(metaclass=AsyncSyncMeta):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        run_manager: Optional[RunManager] = None,
    ):
        logging_connection = KVLoggingSingleton()
        run_manager = run_manager or RunManager(logging_connection)

        self.config = config
        self.providers = providers
        self.pipelines = pipelines
        self.logging_connection = KVLoggingSingleton()
        self.run_manager = run_manager
        self.app = FastAPI()

        self.ingestion_service = IngestionService(
            config, providers, pipelines, run_manager, logging_connection
        )
        self.retrieval_service = RetrievalService(
            config, providers, pipelines, run_manager, logging_connection
        )

        self._setup_routes()
        self._apply_cors()

    def _setup_routes(self):
        from .api.routes import ingestion, retrieval

        self.app.include_router(ingestion.router, prefix="/v1")
        self.app.include_router(retrieval.router, prefix="/v1")

    @syncable
    async def aingest_documents(self, *args, **kwargs):
        return await self.ingestion_service.ingest_documents(*args, **kwargs)

    @syncable
    async def aupdate_documents(self, *args, **kwargs):
        return await self.ingestion_service.update_documents(*args, **kwargs)

    @syncable
    async def aingest_files(self, *args, **kwargs):
        return await self.ingestion_service.ingest_files(*args, **kwargs)

    @syncable
    async def aupdate_files(self, *args, **kwargs):
        return await self.ingestion_service.update_files(*args, **kwargs)

    @syncable
    async def asearch(self, *args, **kwargs):
        return await self.retrieval_service.search(*args, **kwargs)

    @syncable
    async def arag(self, *args, **kwargs):
        return await self.retrieval_service.rag(*args, **kwargs)

    @syncable
    async def aevaluate(self, *args, **kwargs):
        return await self.retrieval_service.evaluate(*args, **kwargs)

    def _apply_cors(self):
        from fastapi.middleware.cors import CORSMiddleware

        origins = ["*", "http://localhost:3000", "http://localhost:8000"]
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def serve(self, host: str = "0.0.0.0", port: int = 8000):
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)
