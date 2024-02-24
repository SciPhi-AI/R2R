from r2r.main import E2EPipelineFactory

# Creates a pipeline with default configuration
# This is the main entry point for the application
# The pipeline is built using the `config.json` file
app = E2EPipelineFactory.create_pipeline()
