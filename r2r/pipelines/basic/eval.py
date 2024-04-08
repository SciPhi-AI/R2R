from typing import Any, Optional

from r2r.core import (
    EvalPipeline,
    LoggingDatabaseConnection,
    log_execution_to_db,
)


class BasicEvalPipeline(EvalPipeline):
    eval_providers = ["deepeval", "parea", "none"]

    def __init__(
        self,
        eval_config: dict,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        frequency = eval_config["frequency"]
        super().__init__(frequency, logging_connection, *args, **kwargs)
        provider = eval_config["provider"]
        if provider not in self.eval_providers:
            raise ValueError(
                f"EvalProvider {provider} not supported in `BasicEvalPipeline`."
            )

        if provider == "deepeval":
            try:
                from r2r.eval import DeepEvalProvider
            except ImportError:
                raise ImportError(
                    "DeepEval is not installed. Please install it using `pip install deepeval`."
                )
            self.eval_provider = DeepEvalProvider(
                provider,
                eval_config.get("sampling_fraction", 1.0),
            )

        elif provider == "parea":
            try:
                from r2r.eval import PareaEvalProvider
            except ImportError:
                raise ImportError(
                    "Parea is not installed. Please install it using `pip install parea`."
                )
            self.eval_provider = PareaEvalProvider(
                provider,
                eval_config.get("sampling_fraction", 1.0),
            )
        else:
            self.eval_provider = None

    @log_execution_to_db
    def evaluate(self, query: str, context: str, completion: str) -> Any:
        return self.eval_provider.evaluate(query, context, completion)
