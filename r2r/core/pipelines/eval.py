import logging
import uuid
from abc import abstractmethod
from typing import Any, Optional

from ..providers.logging import LoggingDatabaseConnection
from .pipeline import Pipeline

logger = logging.getLogger(__name__)


class EvalPipeline(Pipeline):
    def __init__(
        self,
        logging_provider: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        super().__init__(logging_provider=logging_provider, **kwargs)

    def initialize_pipeline(
        self, run_id: Optional[str], *args, **kwargs
    ) -> None:
        self.pipeline_run_info = {
            "run_id": kwargs["run_id"] if "run_id" in kwargs else uuid.uuid4(),
            "type": "evaluation",
        }

    @abstractmethod
    def evaluate(self, query: str, context: str, completion: str) -> Any:
        pass

    def run(
        self,
        query: str,
        context: str,
        completion: str,
        run_id: Optional[str],
        **kwargs,
    ):
        self.initialize_pipeline(run_id)
        logger.debug(
            f"Running the `EvaluationPipeline` with id={self.pipeline_run_info}."
        )
        self.evaluate(query, context, completion)
