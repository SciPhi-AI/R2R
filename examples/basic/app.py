from r2r.main import PipelineFactory

# Creates a pipeline with default configuration
# This is the main entry point for the application
# The pipeline is built using the `config.json` file
app = PipelineFactory.create_pipeline()
