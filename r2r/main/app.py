from fastapi import FastAPI

from .engine import R2REngine


class R2RApp:
    def __init__(self, engine: R2REngine):
        self.engine = engine
        self._setup_routes()
        self._apply_cors()

    def serve(self, host: str = "0.0.0.0", port: int = 8000):
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)

    def _setup_routes(self):
        from .api.routes import auth, ingestion, management, retrieval

        self.app = FastAPI()

        # Create routers with the engine
        ingestion_router = ingestion.IngestionRouter.build_router(self.engine)
        management_router = management.ManagementRouter.build_router(
            self.engine
        )
        retrieval_router = retrieval.RetrievalRouter.build_router(self.engine)
        auth_router = auth.AuthRouter.build_router(self.engine)

        # Include routers in the app
        self.app.include_router(ingestion_router, prefix="/v1")
        self.app.include_router(management_router, prefix="/v1")
        self.app.include_router(retrieval_router, prefix="/v1")
        self.app.include_router(auth_router, prefix="/v1")

        @self.app.router.get("/v1/openapi_spec")
        async def openapi_spec():
            from fastapi.openapi.utils import get_openapi

            return get_openapi(
                title="R2R Application API",
                version="1.0.0",
                routes=self.app.routes,
            )

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
