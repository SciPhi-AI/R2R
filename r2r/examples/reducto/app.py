from r2r.core.adapters import ReductoAdapter
from r2r.main import E2EPipelineFactory, R2RConfig
from r2r.pipelines import IngestionType

app = E2EPipelineFactory.create_pipeline(
    config=R2RConfig.load_config(),
    adapters={
        IngestionType.PDF: ReductoAdapter(),
    },
)
