import argparse
import os

import uvicorn

from r2r.main import E2EPipelineFactory, R2RConfig
from r2r.pipelines import (
    AgentRAGPipeline,
    HyDEPipeline,
    QnARAGPipeline,
    WebRAGPipeline,
)

current_file_path = os.path.dirname(__file__)
configs_path = os.path.join(current_file_path, "..", "configs")

CONFIG_OPTIONS = {
    "default": None,
    "local_ollama_lancedb": os.path.join(configs_path, "local_ollama_lancedb.json"),
    "local_ollama": os.path.join(configs_path, "local_ollama.json"),
    "local_ollama_qdrant": os.path.join(configs_path, "local_ollama_qdrant.json"),
    "local_ollama_with_rerank": os.path.join(
        configs_path, "local_ollama_with_rerank.json"
    ),
    "local_llama_cpp": os.path.join(configs_path, "local_llama_cpp.json"),
}

PIPELINE_OPTIONS = {
    "qna": QnARAGPipeline,
    "web": WebRAGPipeline,
    "agent": AgentRAGPipeline,
    "hyde": HyDEPipeline,
}



def create_app(config_name: str = "default", pipeline_name: str = "qna"):
    config_name = os.getenv("CONFIG_OPTION") or config_name
    pipeline_name = os.getenv("PIPELINE_OPTION") or pipeline_name

    config_path = CONFIG_OPTIONS[config_name]
    pipeline_impl = PIPELINE_OPTIONS[pipeline_name]

    # delete past dataset for testing
    if os.path.exists(os.getenv('LANCEDB_URI')):
            os.remove(os.getenv('LANCEDB_URI'))
            
    app = E2EPipelineFactory.create_pipeline(
        config=R2RConfig.load_config(config_path),
        rag_pipeline_impl=pipeline_impl,
    )
    print('app created...')
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="R2R Pipeline")
    parser.add_argument(
        "--config",
        type=str,
        default="default",
        choices=CONFIG_OPTIONS.keys(),
        help="Configuration option for the pipeline",
    )
    parser.add_argument(
        "--pipeline",
        type=str,
        default="qna",
        choices=PIPELINE_OPTIONS.keys(),
        help="Pipeline implementation to be deployed",
    )
    parser.add_argument(
        "--port",
        type=str,
        default="8000",
        help="Port to serve deployed pipeline on.",
    )

    args, _ = parser.parse_known_args()

    port = os.getenv("PORT") or args.port

    app = create_app(args.config, args.pipeline)
    uvicorn.run(app, host="0.0.0.0", port=int(port))
