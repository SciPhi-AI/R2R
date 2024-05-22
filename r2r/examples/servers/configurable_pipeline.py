import argparse
import os

from r2r import (
    R2RApp,
    R2RConfig,
    R2RPipeFactory,
    R2RPipelineFactory,
    R2RProviderFactory,
)

current_file_path = os.path.dirname(__file__)
configs_path = os.path.join(current_file_path, "..", "configs")


def default_app():  # config_name: str = "default", pipe_name: str = "qna"):
    # config_name = os.getenv("CONFIG_OPTION") or config_name
    # pipe_name = os.getenv("PIPELINE_OPTION") or pipe_name

    config = R2RConfig.from_json()

    providers = R2RProviderFactory(config).create_providers()
    pipes = R2RPipeFactory(config, providers).create_pipes()
    pipelines = R2RPipelineFactory(config, pipes).create_pipelines()

    r2r = R2RApp(
        config=config,
        providers=providers,
        pipelines=pipelines,
    )

    return r2r


r2r = default_app()  # args.config)
app = r2r.app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="R2R Pipe")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Port to serve deployed pipe on.",
    )
    parser.add_argument(
        "--port",
        type=str,
        default="8000",
        help="Port to serve deployed pipe on.",
    )
    # parser.add_argument(
    #     "--config",
    #     type=str,
    #     default="default",
    #     choices=CONFIG_OPTIONS.keys(),
    #     help="Configuration option for the pipe",
    # )

    args, _ = parser.parse_known_args()

    host = os.getenv("HOST") or args.host
    port = os.getenv("PORT") or args.port

    r2r.serve()
