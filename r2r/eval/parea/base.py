import os
from typing import Union

from r2r.core.providers.eval import EvalProvider


class PareaEvalProvider(EvalProvider):
    def __init__(self, provider: str, sampling_fraction: float = 1.0):
        super().__init__(provider, sampling_fraction)
        try:
            from parea.evals.general import answer_relevancy_factory
            from parea.evals.rag import (
                answer_context_faithfulness_statement_level_factory,
                context_query_relevancy_factory,
                context_ranking_pointwise_factory,
            )
            from parea.schemas.log import Log

            self.answer_relevancy = answer_relevancy_factory()
            self.context_query_relevancy = context_query_relevancy_factory()
            self.context_ranking_pointwise = (
                context_ranking_pointwise_factory()
            )
            self.answer_context_faithfulness_statement_level = (
                answer_context_faithfulness_statement_level_factory()
            )

            def create_log(query: str, context: str, completion: str) -> Log:
                return Log(
                    inputs={
                        "question": query,
                        "context": context,
                    },
                    output=completion,
                )

            self._create_log = create_log
        except ImportError:
            raise ImportError(
                "Parea is not installed. Please install it using `pip install parea`."
            )
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "Please set the `OPENAI_API_KEY` environment variable to run with Parea."
            )

    def _evaluate(
        self, query: str, context: str, completion: str
    ) -> dict[str, dict[str, Union[str, float]]]:
        log = self._create_log(query, context, completion)

        answer_relevancy_score = self.answer_relevancy(log)
        context_query_relevancy_score = self.context_query_relevancy(log)
        context_ranking_pointwise_score = self.context_ranking_pointwise(log)
        answer_context_faithfulness_statement_level_score = (
            self.answer_context_faithfulness_statement_level(log)
        )

        return {
            "context_query_relevancy": {
                "score": context_query_relevancy_score,
            },
            "context_ranking": {
                "score": context_ranking_pointwise_score,
            },
            "answer_relevancy": {
                "score": answer_relevancy_score,
            },
            "answer_context_faithfulness": {
                "score": answer_context_faithfulness_statement_level_score,
            },
        }
