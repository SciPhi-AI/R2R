import logging
import os
from typing import Optional
import threading

from fastapi import FastAPI

from .assembly import R2RBuilder, R2RConfig
from hatchet.base import worker

logger = logging.getLogger(__name__)

def start_hatchet_worker():
    worker.start()

def r2r_app(
    config_name: Optional[str] = "default",
    config_path: Optional[str] = None,
) -> FastAPI:
    config = R2RConfig.load(config_name, config_path)

    if (
        config.embedding.provider == "openai"
        and "OPENAI_API_KEY" not in os.environ
    ):
        raise ValueError(
            "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
        )

    # Build the FastAPI app
    app = R2RBuilder(config=config).build().app

    # Start the Hatchet worker in a separate thread
    worker_thread = threading.Thread(target=start_hatchet_worker, daemon=True)
    worker_thread.start()

    return app

logging.basicConfig(level=logging.INFO)

config_name = os.getenv("CONFIG_NAME", None)
config_path = os.getenv("CONFIG_PATH", None)
if not config_path and not config_name:
    config_name = "default"
host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", "8000"))
pipeline_type = os.getenv("PIPELINE_TYPE", "qna")

logger.info(f"Environment CONFIG_NAME: {config_name}")
logger.info(f"Environment CONFIG_PATH: {config_path}")
logger.info(f"Environment PIPELINE_TYPE: {pipeline_type}")

app = r2r_app(
    config_name=config_name,
    config_path=config_path,
)