"""A simple example to demonstrate the usage of `WebSearchRAGPipeline`."""
from r2r.main import E2EPipelineFactory
from r2r.pipelines import WebSearchRAGPipeline

# Creates a pipeline using the `WebSearchRAGPipeline` implementation
app = E2EPipelineFactory.create_pipeline(
    rag_pipeline_impl=WebSearchRAGPipeline
)
