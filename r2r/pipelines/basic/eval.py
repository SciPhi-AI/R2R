import os
from typing import Any

from r2r.core import log_execution_to_db
from r2r.core import EvalProvider, EvalPipeline


class BasicEvalPipeline(EvalPipeline):
    def __init__(self, eval_provider: EvalProvider, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eval_provider = eval_provider

    @log_execution_to_db
    def evaluate(self, query: str, context: str, completion: str) -> Any:
        return self.eval_provider.evaluate(query, context, completion)