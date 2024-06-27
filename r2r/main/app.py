from fastapi import FastAPI

from .engine import R2REngine


class R2RApp:
    def __init__(self, engine: R2REngine):
        self.engine = engine
        self.app = FastAPI()
        self._setup_routes()
        self._apply_cors()

    async def openapi_spec(self, *args, **kwargs):
        from fastapi.openapi.utils import get_openapi

        return get_openapi(
            title="R2R Application API",
            version="1.0.0",
            routes=self.app.routes,
        )

    def _setup_routes(self):
        from .api.routes import ingestion, management, retrieval

        # Pass the engine instance to the route functions
        ingestion.setup_routes(self.app, self.engine)
        retrieval.setup_routes(self.app, self.engine)
        management.setup_routes(self.app, self.engine)
        self.app.get("/openapi_spec")(self.openapi_spec)

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
