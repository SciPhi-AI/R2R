import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .assembly import R2RBuilder, R2RConfig

logger = logging.getLogger(__name__)

# Global scheduler
scheduler = AsyncIOScheduler()

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup
#     r2r_app = await create_r2r_app(
#         config_name=config_name,
#         config_path=config_path,
#     )

#     # Copy all routes from r2r_app to app
#     app.router.routes = r2r_app.app.routes

#     # Copy middleware and exception handlers
#     app.middleware = r2r_app.app.middleware  # type: ignore
#     app.exception_handlers = r2r_app.app.exception_handlers

#     # Start the scheduler
#     scheduler.start()

#     # Start the Hatchet worker
#     await r2r_app.orchestration_provider.start_worker()

#     yield

#     # # Shutdown
#     scheduler.shutdown()


async def create_r2r_app(
    config_name: Optional[str] = "default",
    config_path: Optional[str] = None,
):
    config = R2RConfig.load(config_name, config_path)

    if (
        config.embedding.provider == "openai"
        and "OPENAI_API_KEY" not in os.environ
    ):
        raise ValueError(
            "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
        )

    # Build the R2RApp
    builder = R2RBuilder(config=config)
    return await builder.build()


# Create the FastAPI app
app = FastAPI()

worker_task = None


@app.on_event("startup")
async def start_scheduler():
    # scheduler = AsyncIOScheduler(timezone="Europe/Stockholm")
    # scheduler.add_job(...)
    # scheduler.start()
    # app.state.scheduler = scheduler

    logging.basicConfig(level=logging.INFO)

    config_name = os.getenv("CONFIG_NAME", None)
    config_path = os.getenv("CONFIG_PATH", None)
    if not config_path and not config_name:
        config_name = "default"
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "7272"))

    logger.info(
        f"Environment CONFIG_NAME: {'None' if config_name is None else config_name}"
    )
    logger.info(
        f"Environment CONFIG_PATH: {'None' if config_path is None else config_path}"
    )

    print("Starting scheduler")
    r2r_app = await create_r2r_app(
        config_name=config_name,
        config_path=config_path,
    )

    # Copy all routes from r2r_app to app
    app.router.routes = r2r_app.app.routes

    # Copy middleware and exception handlers
    app.middleware = r2r_app.app.middleware  # type: ignore
    app.exception_handlers = r2r_app.app.exception_handlers

    print("Starting worker_task")
    app.state.worker_task = await r2r_app.orchestration_provider.start_worker()
    # print("Starting worker_task", app.state.worker_task)
    # Start the scheduler
    scheduler.start()


@app.on_event("shutdown")
async def stop_scheduler():
    # # Shutdown
    # print("Stopping worker_task", app.state.worker_task)
    print("Stopping scheduler")
    scheduler.shutdown()

    # app.state.worker_task.cancel()


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
