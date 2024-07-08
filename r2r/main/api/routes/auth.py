from typing import Optional

from fastapi import Depends, File, UploadFile

from r2r.base import R2RException

from ...auth.base import AuthHandler
from ...engine import R2REngine
from ...services.ingestion_service import IngestionService
from ..requests import R2RIngestFilesRequest, R2RUpdateFilesRequest
from .base_router import BaseRouter


class AuthRouter(BaseRouter):
    def __init__(
        self, engine: R2REngine, auth_handler: Optional[AuthHandler] = None
    ):
        super().__init__(engine, auth_handler)
        self.setup_routes()

    def setup_routes(self):
        # Add login and register endpoints only if authentication is enabled
        @self.router.post("/register")
        def register(auth_details: dict):
            # Implement user registration logic here
            return {"message": "User registered successfully"}

        @self.router.post("/login")
        def login(auth_details: dict):
            if (
                auth_details["username"] == "admin"
                and auth_details["password"] == "admin"
            ):
                token = self.auth_handler.encode_token(
                    auth_details["username"]
                )
                return {"token": token}
            raise R2RException(
                message="Invalid username and/or password", status_code=401
            )
