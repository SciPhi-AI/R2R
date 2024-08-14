from .client import R2RClient, handle_request_error
from .routes.auth.base import AuthRouter
from .routes.base_router import BaseRouter
from .routes.ingestion.base import IngestionRouter
from .routes.management.base import ManagementRouter
from .routes.retrieval.base import RetrievalRouter

__all__ = [
    # Client
    "R2RClient",
    "handle_request_error",
    # Routes
    "AuthRouter",
    "IngestionRouter",
    "ManagementRouter",
    "RetrievalRouter",
    "BaseRouter",
]
