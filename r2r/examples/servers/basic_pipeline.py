import uvicorn

from r2r.main import E2EPipelineFactory, R2RConfig

# Creates a pipeline with default configuration
# This is the main entry point for the application
# The pipeline is built using the `config.json` file
# Read more about the configuration in the documentation [https://r2r-docs.sciphi.ai/core-features/factory]
app = E2EPipelineFactory.create_pipeline(config=R2RConfig.load_config())


if __name__ == "__main__":
    # Run the FastAPI application using Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
