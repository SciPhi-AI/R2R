from typing import Any, Optional

from r2r.core import (
    EvalPipeline,
    EvalProvider,
    LoggingDatabaseConnection,
    log_execution_to_db,
)


class BasicEvalPipeline(EvalPipeline):
    def __init__(
        self,
        eval_provider: Optional[EvalProvider] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.eval_provider = eval_provider
    @log_execution_to_db
    def evaluate(self, query: str, context: str, completion: str) -> Any:
        return self.eval_provider.evaluate(query, context, completion)
