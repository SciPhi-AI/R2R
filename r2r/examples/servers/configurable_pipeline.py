import argparse
import os
import logging
from enum import Enum
from r2r import (
    R2RConfig,
    R2RAppBuilder,
    # For Web Search
    R2RWebSearchPipe,
    SerperClient,
    # For HyDE & the like.
    R2RPipeFactoryWithMultiSearch
)

logger = logging.getLogger(__name__)

current_file_path = os.path.dirname(__file__)
configs_path = os.path.join(current_file_path, "..", "..", "..")

CONFIG_OPTIONS = {
    "default": None,
    "local_ollama": os.path.join(configs_path, "local_ollama.json"),
}

class PipelineType(Enum):
    QNA = "qna"
    WEB = "web"
    HYDE = "hyde"

def r2r_app(config_name: str = "default", pipeline_type: PipelineType = PipelineType.QNA):
    if config_path := CONFIG_OPTIONS.get(config_name):
        logger.info(f"Using config path: {config_path}")
        config = R2RConfig.from_json(config_path)
    else:
        default_config_path = os.path.join(configs_path, "config.json")
        logger.info(f"Using default config path: {default_config_path}")
        config = R2RConfig.from_json(default_config_path)

    if config.embedding.provider == 'openai' and 'OPENAI_API_KEY' not in os.environ:
        raise ValueError("Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider.")

    if pipeline_type == PipelineType.QNA:
        return R2RAppBuilder(config).build()
    elif pipeline_type == PipelineType.WEB:
        # Create search pipe override and pipes
        web_search_pipe = R2RWebSearchPipe(
            serper_client=SerperClient()  # TODO - Develop a `WebSearchProvider` for configurability
        )
        return R2RAppBuilder(config).with_search_pipe(web_search_pipe).build()
    elif pipeline_type == PipelineType.HYDE:
        return R2RAppBuilder(config).with_pipe_factory(R2RPipeFactoryWithMultiSearch) \
            .build(
                # Add optional override arguments which propagate to the pipe factory
                task_prompt_name="hyde",
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

    r2r = r2r_app(config_name, PipelineType(pipeline_type))
    app = r2r.app

    r2r.serve(host, int(port))