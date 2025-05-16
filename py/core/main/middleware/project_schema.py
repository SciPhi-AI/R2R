from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import re
import logging

logger = logging.getLogger(__name__)

from contextvars import ContextVar

# TODO: Probably should be grabbing this from the config
project_schema_context: ContextVar[str] = ContextVar("project_schema", default="r2r_default")

def get_current_project_schema() -> str:
    """Get the current project schema name from context."""
    return project_schema_context.get()

class ProjectSchemaMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, 
        app: FastAPI, 
        default_schema: str = "r2r_default",
        schema_exists_func = None
    ):
        super().__init__(app)
        self.default_schema = default_schema
        self.schema_exists_func = schema_exists_func
        
    async def dispatch(self, request: Request, call_next):
        # Skip schema check for static files, docs, etc.
        if request.url.path.startswith(("/docs", "/redoc", "/static", "/openapi.json")):
            return await call_next(request)
            
        schema_name = request.headers.get("x-project-name", self.default_schema)
        
        # Prevent SQL injection by validating the schema name
        if not re.match(r'^[a-zA-Z0-9_]+$', schema_name):
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid schema name format"}
            )
        
        # Set the project schema in the context for this request
        token = project_schema_context.set(schema_name)
        
        try:
            return await call_next(request)
        finally:
            # Reset context when done
            project_schema_context.reset(token)
