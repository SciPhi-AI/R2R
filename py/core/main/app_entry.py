import os
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.base import FUSEException
from core.utils.logging_config import configure_logging

from .assembly import FUSEBuilder, FUSEConfig

logger, log_file = configure_logging()


# Global scheduler
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    fuse_app = await create_fuse_app(
        config_name=config_name,
        config_path=config_path,
    )

    # Copy all routes from fuse_app to app
    app.router.routes = fuse_app.app.routes

    # Copy middleware and exception handlers
    app.middleware = fuse_app.app.middleware  # type: ignore
    app.exception_handlers = fuse_app.app.exception_handlers

    # Start the scheduler
    scheduler.start()

    # Start the Hatchet worker
    await fuse_app.orchestration_provider.start_worker()

    yield

    # # Shutdown
    scheduler.shutdown()


async def create_fuse_app(
    config_name: Optional[str] = "default",
    config_path: Optional[str] = None,
):
    config = FUSEConfig.load(config_name=config_name, config_path=config_path)

    if (
        config.embedding.provider == "openai"
        and "OPENAI_API_KEY" not in os.environ
    ):
        raise ValueError(
            "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
        )

    # Build the FUSEApp
    builder = FUSEBuilder(config=config)
    return await builder.build()


config_name = os.getenv("FUSE_CONFIG_NAME", None)
config_path = os.getenv("FUSE_CONFIG_PATH", None)

if not config_path and not config_name:
    config_name = "default"
host = os.getenv("FUSE_HOST", os.getenv("HOST", "0.0.0.0"))
port = int(os.getenv("FUSE_PORT", "7272"))

logger.info(
    f"Environment FUSE_CONFIG_NAME: {'None' if config_name is None else config_name}"
)
logger.info(
    f"Environment FUSE_CONFIG_PATH: {'None' if config_path is None else config_path}"
)
logger.info(f"Environment FUSE_PROJECT_NAME: {os.getenv('FUSE_PROJECT_NAME')}")

logger.info(f"Environment FUSE_POSTGRES_HOST: {os.getenv('FUSE_POSTGRES_HOST')}")
logger.info(
    f"Environment FUSE_POSTGRES_DBNAME: {os.getenv('FUSE_POSTGRES_DBNAME')}"
)
logger.info(f"Environment FUSE_POSTGRES_PORT: {os.getenv('FUSE_POSTGRES_PORT')}")
logger.info(
    f"Environment FUSE_POSTGRES_PASSWORD: {os.getenv('FUSE_POSTGRES_PASSWORD')}"
)
logger.info(
    f"Environment FUSE_PROJECT_NAME: {os.getenv('FUSE_PFUSE_PROJECT_NAME')}"
)

# Create the FastAPI app
app = FastAPI(
    lifespan=lifespan,
    log_config=None,
)


@app.exception_handler(FUSEException)
async def fuse_exception_handler(request: Request, exc: FUSEException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": exc.message,
            "error_type": type(exc).__name__,
        },
    )


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
