import inspect
from unittest.mock import Mock, create_autospec

import pytest
from starlette.responses import FileResponse, StreamingResponse
from starlette.templating import _TemplateResponse

from core import R2RProviders
from core.main.abstractions import R2RServices
from core.main.api.v3.chunks_router import ChunksRouter
from core.main.api.v3.collections_router import CollectionsRouter
from core.main.api.v3.conversations_router import ConversationsRouter
from core.main.api.v3.documents_router import DocumentsRouter
from core.main.api.v3.graph_router import GraphRouter
from core.main.api.v3.indices_router import IndicesRouter
from core.main.api.v3.prompts_router import PromptsRouter
from core.main.api.v3.retrieval_router import RetrievalRouter
from core.main.api.v3.system_router import SystemRouter
from core.main.api.v3.users_router import UsersRouter
from core.main.config import R2RConfig
from core.providers.auth import R2RAuthProvider
from core.providers.database import PostgresDatabaseProvider
from core.providers.email import ConsoleMockEmailProvider
from core.providers.embeddings import OpenAIEmbeddingProvider
from core.providers.ingestion import R2RIngestionProvider
from core.providers.llm import OpenAICompletionProvider
from core.providers.orchestration import SimpleOrchestrationProvider

ROUTERS = [
    UsersRouter,
    ChunksRouter,
    CollectionsRouter,
    ConversationsRouter,
    DocumentsRouter,
    GraphRouter,
    IndicesRouter,
    PromptsRouter,
    RetrievalRouter,
    SystemRouter,
]


@pytest.fixture
def mock_providers():
    # Create mock auth provider that inherits from the base class
    mock_auth = create_autospec(R2RAuthProvider)

    # Create other mock providers
    mock_db = create_autospec(PostgresDatabaseProvider)
    mock_db.config = Mock()
    mock_ingestion = create_autospec(R2RIngestionProvider)
    mock_ingestion.config = Mock()
    mock_embedding = create_autospec(OpenAIEmbeddingProvider)
    mock_embedding.config = Mock()
    mock_completion_embedding = create_autospec(OpenAIEmbeddingProvider)
    mock_completion_embedding.config = Mock()
    mock_llm = create_autospec(OpenAICompletionProvider)
    mock_llm.config = Mock()
    mock_orchestration = create_autospec(SimpleOrchestrationProvider)
    mock_orchestration.config = Mock()
    mock_email = create_autospec(ConsoleMockEmailProvider)
    mock_email.config = Mock()

    # Set up any needed methods
    mock_auth.auth_wrapper = Mock(return_value=lambda: None)

    providers = R2RProviders(
        auth=mock_auth,
        database=mock_db,
        ingestion=mock_ingestion,
        embedding=mock_embedding,
        completion_embedding=mock_completion_embedding,
        llm=mock_llm,
        orchestration=mock_orchestration,
        email=mock_email,
    )
    return providers


@pytest.fixture
def mock_services():
    return R2RServices(
        management=Mock(),
        auth=Mock(),
        ingestion=Mock(),
        retrieval=Mock(),
        graph=Mock(),
    )


@pytest.fixture
def mock_config():
    config_data = {
        "app": {},  # AppConfig needs minimal data
        "auth": {
            "provider": "mock"
        },
        "completion": {
            "provider": "mock"
        },
        "crypto": {
            "provider": "mock"
        },
        "database": {
            "provider": "mock"
        },
        "embedding": {
            "provider": "mock",
            "base_model": "test",
            "base_dimension": 1024,
            "batch_size": 10,
            "add_title_as_prefix": True,
        },
        "completion_embedding": {
            "provider": "mock",
            "base_model": "test",
            "base_dimension": 1024,
            "batch_size": 10,
            "add_title_as_prefix": True,
        },
        "email": {
            "provider": "mock"
        },
        "ingestion": {
            "provider": "mock"
        },
        "logging": {
            "provider": "mock",
            "log_table": "logs"
        },
        "agent": {
            "generation_config": {}
        },
        "orchestration": {
            "provider": "mock"
        },
    }
    return R2RConfig(config_data)


@pytest.fixture(params=ROUTERS)
def router(request, mock_providers, mock_services, mock_config):
    router_class = request.param
    return router_class(mock_providers, mock_services, mock_config)


def test_all_routes_have_base_endpoint_decorator(router):
    for route in router.router.routes:
        if (route.path.endswith("/stream") or route.path.endswith("/viewer")
                or "websocket" in str(type(route)).lower()):
            continue

        endpoint = route.endpoint
        assert hasattr(endpoint, "_is_base_endpoint"), (
            f"Route {route.path} missing @base_endpoint decorator")


def test_all_routes_have_proper_return_type_hints(router):
    for route in router.router.routes:
        if (route.path.endswith("/stream")
                or "websocket" in str(type(route)).lower()):
            continue

        endpoint = route.endpoint
        return_type = inspect.signature(endpoint).return_annotation

        # Check if the type is an R2RResults by name
        is_valid = isinstance(
            return_type, type) and ("R2RResults" in str(return_type)
                                    or "PaginatedR2RResult" in str(return_type)
                                    or return_type == FileResponse
                                    or return_type == StreamingResponse
                                    or return_type == _TemplateResponse)

        assert is_valid, (
            f"Route {route.path} has invalid return type: {return_type}, expected R2RResults[...]"
        )


def test_all_routes_have_rate_limiting(router):
    import warnings

    for route in router.router.routes:
        print(f"Checking route: {route.path}")
        print(f"Dependencies: {route.dependencies}")
        has_rate_limit = any(dep.dependency == router.rate_limit_dependency
                             for dep in route.dependencies)
        if not has_rate_limit:
            # We should require this in the future, but for now just warn
            warnings.warn(
                f"Route {route.path} missing rate limiting - this will be required in the future",
                UserWarning,
            )
