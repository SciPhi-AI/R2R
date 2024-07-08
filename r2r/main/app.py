from fastapi import FastAPI, HTTPException

from .auth.base import AuthHandler
from .engine import R2REngine


class R2RApp:
    def __init__(self, engine: R2REngine, use_auth: bool = True):
        self.engine = engine
        self.use_auth = use_auth
        self.auth_handler = AuthHandler() if use_auth else None
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

        self.app = FastAPI()

        # Create routers with the engine
        ingestion_router = ingestion.IngestionRouter.build_router(
            self.engine, self.auth_handler
        )
        management_router = management.ManagementRouter.build_router(
            self.engine, self.auth_handler
        )
        retrieval_router = retrieval.RetrievalRouter.build_router(
            self.engine, self.auth_handler
        )

        # Include routers in the app
        self.app.include_router(ingestion_router, prefix="/v1")
        self.app.include_router(management_router, prefix="/v1")
        self.app.include_router(retrieval_router, prefix="/v1")

        if self.use_auth:
            # Add login and register endpoints only if authentication is enabled
            @self.app.post("/register")
            def register(auth_details: dict):
                # Implement user registration logic here
                return {"message": "User registered successfully"}

            @self.app.post("/login")
            def login(auth_details: dict):
                if (
                    auth_details["username"] == "admin"
                    and auth_details["password"] == "admin"
                ):
                    token = self.auth_handler.encode_token(
                        auth_details["username"]
                    )
                    return {"token": token}
                raise HTTPException(
                    status_code=401, detail="Invalid username and/or password"
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

    def serve(self, host: str = "0.0.0.0", port: int = 8000):
        import uvicorn

        uvicorn.run(self.app, host=host, port=port)
