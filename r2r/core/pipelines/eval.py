import logging
import random
from abc import abstractmethod
from typing import Any, Optional

from ..providers.eval import EvalProvider
from ..utils import generate_run_id
from ..utils.logging import LoggingDatabaseConnection
from .pipeline import Pipeline

logger = logging.getLogger(__name__)


class EvalPipeline(Pipeline):
    def __init__(
        self,
        eval_provider: EvalProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.eval_provider = eval_provider
        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipeline(
        self, run_id: Optional[str], *args, **kwargs
    ) -> None:
        self.pipeline_run_info = {
            "run_id": run_id or generate_run_id(),
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
        if random.random() < self.eval_provider.config.sampling_fraction:
            return self.evaluate(query, context, completion)
        return None

    def run_stream(
        self,
        query: str,
        context: str,
        completion: str,
        run_id: Optional[str],
        **kwargs,
    ):
        raise NotImplementedError(
            "Streaming mode not supported for `EvalPipeline`."
        )
