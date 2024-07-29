import logging
import os
from enum import Enum
from typing import Optional

from fastapi import FastAPI

from r2r import R2RBuilder, R2RConfig
from r2r.main.execution import R2RExecutionWrapper

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
    client_mode: bool = False,
    base_url: Optional[str] = None,
    pipeline_type: PipelineType = PipelineType.QNA,
) -> FastAPI:
    if pipeline_type != PipelineType.QNA:
        raise ValueError("Only QNA pipeline is supported in quickstart.")
    if config_path and config_name:
        raise ValueError("Cannot specify both config and config_name")

    config_path = os.getenv("CONFIG_PATH") or config_path
    if config_path:
        config = R2RConfig.from_json(config_path)
    else:
        config_name = os.getenv("CONFIG_NAME") or config_name
        if config_name not in R2RBuilder.CONFIG_OPTIONS:
            raise ValueError(f"Invalid config name: {config_name}")
        config = R2RConfig.from_json(R2RBuilder.CONFIG_OPTIONS[config_name])

    if (
        config.embedding.provider == "openai"
        and "OPENAI_API_KEY" not in os.environ
    ):
        raise ValueError(
            "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
        )

    wrapper = R2RExecutionWrapper(
        config_name=config_name,
        config_path=config_path,
        client_mode=client_mode,
        base_url=base_url,
    )

    return wrapper.get_app()


logging.basicConfig(level=logging.INFO)

config_name = os.getenv("CONFIG_NAME", None)
config_path = os.getenv("CONFIG_PATH", None)
if not config_path and not config_name:
    config_name = "default"
client_mode = os.getenv("CLIENT_MODE", "false").lower() == "true"
base_url = os.getenv("BASE_URL")
host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", "8000"))
pipeline_type = os.getenv("PIPELINE_TYPE", "qna")

logger.info(f"Environment CONFIG_NAME: {config_name}")
logger.info(f"Environment CONFIG_PATH: {config_path}")
logger.info(f"Environment CLIENT_MODE: {client_mode}")
logger.info(f"Environment BASE_URL: {base_url}")
logger.info(f"Environment PIPELINE_TYPE: {pipeline_type}")

app = r2r_app(
    config_name=config_name,
    config_path=config_path,
    client_mode=client_mode,
    base_url=base_url,
    pipeline_type=PipelineType(pipeline_type),
)
