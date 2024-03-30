"""A simple example to demonstrate the usage of `WebSearchRAGPipeline`."""

import uvicorn

from r2r.main import E2EPipelineFactory, R2RConfig
from r2r.pipelines import WebSearchRAGPipeline

# Creates a pipeline using the `WebSearchRAGPipeline` implementation
app = E2EPipelineFactory.create_pipeline(
    config=R2RConfig.load_config(), rag_pipeline_impl=WebSearchRAGPipeline
)


if __name__ == "__main__":
    # Run the FastAPI application using Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
