from typing import Any, Optional

from r2r.core import (
    EvalPipeline,
    EvalProvider,
    LoggingDatabaseConnection,
    log_output_to_db,
)


class BasicEvalPipeline(EvalPipeline):
    def __init__(
        self,
        eval_provider: Optional[EvalProvider] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            eval_provider, logging_connection=logging_connection, **kwargs
        )

    @log_output_to_db
    def evaluate(self, query: str, context: str, completion: str) -> Any:
        return self.eval_provider.evaluate(query, context, completion)
