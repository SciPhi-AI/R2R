# from typing import Any, Optional

# from r2r.core import (
#     EvalPipe,
#     EvalProvider,
#     PipeLoggingConnectionSingleton,
#     log_output_to_db,
# )


# class BasicEvalPipe(EvalPipe):
#     def __init__(
#         self,
#         eval_provider: Optional[EvalProvider] = None,
#         pipe_logger: Optional[PipeLoggingConnectionSingleton] = None,
#         *args,
#         **kwargs,
#     ):
#         super().__init__(
#             eval_provider, pipe_logger=pipe_logger, **kwargs
#         )

#     @log_output_to_db
#     def evaluate(self, query: str, context: str, completion: str) -> Any:
#         return self.eval_provider.evaluate(query, context, completion)
