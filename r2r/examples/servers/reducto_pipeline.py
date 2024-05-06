import uvicorn

from r2r.core.parsers import ReductoParser
from r2r.main import E2EPipelineFactory, R2RConfig
from r2r.pipelines import DocumentType

# Read more about the configuration in the documentation [https://r2r-docs.sciphi.ai/deep-dive/factory]
app = E2EPipelineFactory.create_pipeline(
    config=R2RConfig.from_json(),
    parsers={
        DocumentType.PDF: ReductoParser(),
    },
)


if __name__ == "__main__":
    # Run the FastAPI application using Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
