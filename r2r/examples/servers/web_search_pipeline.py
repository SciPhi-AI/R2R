"""A simple example to demonstrate the usage of `WebRAGPipeline`."""

import uvicorn

from r2r.main import E2EPipelineFactory, R2RConfig
from r2r.pipelines import WebRAGPipeline

# Creates a pipeline using the `WebRAGPipeline` implementation
app = E2EPipelineFactory.create_pipeline(
    config=R2RConfig.load_config(), rag_pipeline_impl=WebRAGPipeline
)


if __name__ == "__main__":
    # Run the FastAPI application using Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)