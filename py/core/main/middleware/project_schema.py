import logging
import re

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.utils.context import project_schema_context, set_project_schema

logger = logging.getLogger(__name__)


class ProjectSchemaMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app, default_schema: str = "r2r_default", schema_exists_func=None
    ):
        super().__init__(app)
        self.default_schema = default_schema
        self.schema_exists_func = schema_exists_func

    async def dispatch(self, request: Request, call_next):
        # Skip schema check for static files, docs, etc.
        if request.url.path.startswith(
            ("/docs", "/redoc", "/static", "/openapi.json")
        ):
            return await call_next(request)

        # Get the project name from the x-project-name header or use default
        schema_name = request.headers.get(
            "x-project-name", self.default_schema
        )

        # Validate schema name format (prevent SQL injection)
        if not re.match(r"^[a-zA-Z0-9_]+$", schema_name):
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid schema name format"},
            )

        # Check if schema exists (optional)
        if self.schema_exists_func and schema_name != self.default_schema:
            try:
                schema_exists = await self.schema_exists_func(schema_name)
                if not schema_exists:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": f"Schema '{schema_name}' does not exist"
                        },
                    )
            except Exception as e:
                logger.error(f"Error checking schema existence: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "detail": "Internal server error checking schema"
                    },
                )

        # Set the project schema in the context for this request
        schema_name = schema_name.replace('"', "")

        token = set_project_schema(schema_name)

        try:
            # Process the request with the set schema
            return await call_next(request)
        finally:
            # Reset context when done
            project_schema_context.reset(token)
