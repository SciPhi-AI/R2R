from r2r.main import E2EPipelineFactory, load_config

# Creates a pipeline with default configuration
# This is the main entry point for the application
# The pipeline is built using the `config.json` file
config = load_config()
app = E2EPipelineFactory.create_pipeline()
