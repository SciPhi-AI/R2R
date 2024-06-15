import argparse
import logging
import os
from enum import Enum

from fastapi import FastAPI

from r2r import (
    R2RAppBuilder,
    R2RConfig,
    R2RPipeFactoryWithMultiSearch,
    R2RWebSearchPipe,
    SerperClient,
)

logger = logging.getLogger(__name__)

current_file_path = os.path.dirname(__file__)
configs_path = os.path.join(current_file_path, "..", "..", "..")

CONFIG_OPTIONS = {
    "default": None,
    "local_ollama": os.path.join(
        current_file_path, "..", "configs", "local_ollama.json"
    ),
    "local_ollama_rerank": os.path.join(
        current_file_path, "..", "configs", "local_ollama_rerank.json"
    ),
    "pgvector": os.path.join(
        current_file_path, "..", "configs", "pgvector.json"
    ),
    "neo4j_kg": os.path.join(
        current_file_path, "..", "configs", "neo4j_kg.json"
    ),
}


class PipelineType(Enum):
    QNA = "qna"
    WEB = "web"
    HYDE = "hyde"


def r2r_app(
    config_name: str = "default",
    pipeline_type: PipelineType = PipelineType.QNA,
) -> FastAPI:
    config_name = os.getenv("CONFIG_OPTION") or config_name

    if config_path := CONFIG_OPTIONS.get(config_name):
        logger.info(f"Using config path: {config_path}")
        config = R2RConfig.from_json(config_path)
    else:
        default_config_path = os.path.join(configs_path, "config.json")
        logger.info(f"Using default config path: {default_config_path}")
        config = R2RConfig.from_json(default_config_path)

    if (
        config.embedding.provider == "openai"
        and "OPENAI_API_KEY" not in os.environ
    ):
        raise ValueError(
            "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
        )

    if pipeline_type == PipelineType.QNA:
        return R2RAppBuilder(config).build().app
    elif pipeline_type == PipelineType.WEB:
        web_search_pipe = R2RWebSearchPipe(
            serper_client=SerperClient()  # TODO - Develop a `WebSearchProvider` for configurability
        )
        return (
            R2RAppBuilder(config).with_search_pipe(web_search_pipe).build().app
        )
    elif pipeline_type == PipelineType.HYDE:
        return (
            R2RAppBuilder(config)
            .with_pipe_factory(R2RPipeFactoryWithMultiSearch)
            .build(
                task_prompt_name="hyde",
            )
            .app
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="R2R Pipe")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to serve deployed pipe on.",
    )
    parser.add_argument(
        "--port",
        type=str,
        default="8000",
        help="Port to serve deployed pipe on.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="default",
        choices=CONFIG_OPTIONS.keys(),
        help="Configuration option for the pipe",
    )
    parser.add_argument(
        "--pipeline_type",
        type=str,
        default="qna",
        choices=[ele.lower() for ele in PipelineType.__members__.keys()],
        help="Specific pipeline to deploy",
    )

    args, _ = parser.parse_known_args()

    host = os.getenv("HOST") or args.host
    port = os.getenv("PORT") or args.port
    config_name = os.getenv("CONFIG_OPTION") or args.config
    pipeline_type = os.getenv("PIPELINE_TYPE") or args.pipeline_type

    logger.info(f"Environment CONFIG_OPTION: {config_name}")

    app = r2r_app(config_name, PipelineType(pipeline_type))

    import uvicorn

    uvicorn.run(app, host=host, port=int(port))
