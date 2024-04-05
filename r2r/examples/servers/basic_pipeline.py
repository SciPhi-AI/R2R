import argparse
import os

import uvicorn

from r2r.main import E2EPipelineFactory, R2RConfig

current_file_path = os.path.dirname(__file__)
configs_path = os.path.join(current_file_path, "..", "configs")

OPTIONS = {
    "default": None,
    "local_ollama": os.path.join(configs_path, "local_ollama.json"),
    "local_llama_cpp": os.path.join(configs_path, "local_llama_cpp.json"),
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="R2R Pipeline")
    parser.add_argument(
        "--config",
        type=str,
        default="default",
        choices=OPTIONS.keys(),
        help="Configuration option for the pipeline",
    )
    args = parser.parse_args()

    config_path = OPTIONS[args.config]

    # Creates a pipeline with the specified configuration
    # This is the main entry point for the application
    # The pipeline is built using the specified configuration file
    # Read more about the configuration in the documentation [https://r2r-docs.sciphi.ai/core-features/factory]
    app = E2EPipelineFactory.create_pipeline(
        config=R2RConfig.load_config(config_path)
    )

    # Run the FastAPI application using Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
