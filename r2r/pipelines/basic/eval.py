import os
from typing import Any

from r2r.core import log_execution_to_db
from r2r.core.pipelines.eval import EvalPipeline


class DeepEvaluationPipeline(EvalPipeline):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            from deepeval import evaluate

            self.deepeval_evaluate = evaluate
            from deepeval.metrics import (
                AnswerRelevancyMetric,
                HallucinationMetric,
            )

            self.AnswerRelevancyMetric = AnswerRelevancyMetric
            self.HallucinationMetric = HallucinationMetric
            from deepeval.test_case import LLMTestCase

            self.LLMTestCase = LLMTestCase
        except ImportError:
            raise ImportError(
                "DeepEval is not installed. Please install it using `pip install deepeval`."
            )
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "Please set the `OPENAI_API_KEY` environment variable to run with DeepEval."
            )

    @log_execution_to_db
    def evaluate(self, query: str, context: str, completion: str) -> Any:
        test_case = self.LLMTestCase(
            input=query,
            actual_output=completion,
            context=[context],
            retrieval_context=[context],
        )

        answer_relevancy_metric = self.AnswerRelevancyMetric()
        hallucination_metric = self.HallucinationMetric()

        answer_relevancy_result = self.deepeval_evaluate(
            [test_case], [answer_relevancy_metric]
        )
        hallucination_result = self.deepeval_evaluate(
            [test_case], [hallucination_metric]
        )

        return {
            "answer_relevancy": {
                "score": answer_relevancy_result[0].metrics[0].score,
                "reason": answer_relevancy_result[0].metrics[0].reason,
            },
            "hallucination": {
                "score": hallucination_result[0].metrics[0].score,
                "reason": hallucination_result[0].metrics[0].reason,
            },
        }
