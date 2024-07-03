import logging
import os
from enum import Enum
from typing import Optional

from fastapi import FastAPI

from r2r import R2RBuilder, R2RConfig
from r2r.examples.quickstart import R2RQuickstart

logger = logging.getLogger(__name__)
current_file_path = os.path.dirname(__file__)
configs_path = os.path.join(current_file_path, "..", "..", "..")


class PipelineType(Enum):
    QNA = "qna"
    WEB = "web"
    HYDE = "hyde"


def r2r_app(
    config_option: Optional[str] = "default",
    config_path: Optional[str] = None,
    client_server_mode: bool = False,
    base_url: Optional[str] = None,
    pipeline_type: PipelineType = PipelineType.QNA,
) -> FastAPI:
    if pipeline_type != PipelineType.QNA:
        raise ValueError("Only QNA pipeline is supported in quickstart.")
    if config_path and config_option:
        raise ValueError("Cannot specify both config and config_option")

    if config_path:
        config = R2RConfig.from_json(config_path)
    else:
        config_option = os.getenv("CONFIG_NAME") or config_option
        if config_option not in R2RBuilder.CONFIG_OPTIONS:
            raise ValueError(f"Invalid config name: {config_option}")
        config = R2RConfig.from_json(R2RBuilder.CONFIG_OPTIONS[config_option])

    if (
        config.embedding.provider == "openai"
        and "OPENAI_API_KEY" not in os.environ
    ):
        raise ValueError(
            "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
        )

    quickstart = R2RQuickstart(
        config_name=config_option,
        config_path=config_path,
        client_server_mode=client_server_mode,
        base_url=base_url,
    )

    return quickstart.get_app()


logging.basicConfig(level=logging.INFO)

config_option = os.getenv("CONFIG_OPTION", "default")
if config_option == "":
    config_option = "default"
config_path = os.getenv("CONFIG_PATH")
client_server_mode = os.getenv("CLIENT_SERVER_MODE", "false").lower() == "true"
base_url = os.getenv("BASE_URL")
host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", "8000"))
pipeline_type = os.getenv("PIPELINE_TYPE", "qna")

logger.info(f"Environment CONFIG_OPTION: {config_option}")
logger.info(f"Environment CONFIG_PATH: {config_path}")
logger.info(f"Environment CLIENT_SERVER_MODE: {client_server_mode}")
logger.info(f"Environment BASE_URL: {base_url}")
logger.info(f"Environment PIPELINE_TYPE: {pipeline_type}")

app = r2r_app(
    config_option=config_option,
    config_path=config_path,
    client_server_mode=client_server_mode,
    base_url=base_url,
    pipeline_type=PipelineType(pipeline_type),
)
