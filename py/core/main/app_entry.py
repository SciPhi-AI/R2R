import logging
import os
from typing import Optional

from fastapi import FastAPI

from .assembly import R2RBuilder, R2RConfig

logger = logging.getLogger(__name__)


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
    app = R2RBuilder(config=config).build()

    # Start the Hatchet worker in a separate thread
    app.orchestration_provider.start_worker()

    return app.app


logging.basicConfig(level=logging.INFO)

config_name = os.getenv("CONFIG_NAME", None)
config_path = os.getenv("CONFIG_PATH", None)
if not config_path and not config_name:
    config_name = "default"
host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", "7272"))
pipeline_type = os.getenv("PIPELINE_TYPE", "qna")

logger.info(f"Environment CONFIG_NAME: {config_name}")
logger.info(f"Environment CONFIG_PATH: {config_path}")
logger.info(f"Environment PIPELINE_TYPE: {pipeline_type}")

app = r2r_app(
    config_name=config_name,
    config_path=config_path,
)
