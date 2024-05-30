from r2r import (
    R2RApp,
    R2RConfig,
    R2RPipeFactory,
    R2RPipelineFactory,
    R2RProviderFactory,
)

config = R2RConfig.from_json()

providers = R2RProviderFactory(config).create_providers()
pipes = R2RPipeFactory(config, providers).create_pipes()
pipelines = R2RPipelineFactory(config, pipes).create_pipelines()
r2r = R2RApp(config, providers, pipelines)
app = r2r.app
# app.serve
