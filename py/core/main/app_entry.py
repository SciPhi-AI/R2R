import logging
import os
from enum import Enum
from typing import Optional

from fastapi import FastAPI

from .assembly import R2RBuilder, R2RConfig
from .r2r import R2R

logger = logging.getLogger(__name__)
current_file_path = os.path.dirname(__file__)
configs_path = os.path.join(current_file_path, "..", "..", "..")


class PipelineType(Enum):
    QNA = "qna"
    WEB = "web"
    HYDE = "hyde"


def r2r_app(
    config_name: Optional[str] = "default",
    config_path: Optional[str] = None,
    pipeline_type: PipelineType = PipelineType.QNA,
) -> FastAPI:
    if pipeline_type != PipelineType.QNA:
        raise ValueError("Only QNA pipeline is supported in quickstart.")
    if config_path and config_name:
        raise ValueError("Cannot specify both config and config_name")

    if config_path := os.getenv("CONFIG_PATH") or config_path:
        config = R2RConfig.from_toml(config_path)
    else:
        config_name = os.getenv("CONFIG_NAME") or config_name
        if config_name not in R2RBuilder.CONFIG_OPTIONS:
            raise ValueError(f"Invalid config name: {config_name}")
        config = R2RConfig.from_toml(R2RBuilder.CONFIG_OPTIONS[config_name])

    if (
        config.embedding.provider == "openai"
        and "OPENAI_API_KEY" not in os.environ
    ):
        raise ValueError(
            "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
        )

    r2r_deployment = R2R(config=config)

    # Return the FastAPI app
    return r2r_deployment.app.app


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
    pipeline_type=PipelineType(pipeline_type),
)
