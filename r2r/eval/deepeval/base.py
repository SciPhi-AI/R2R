import os

from r2r.core import EvalProvider


class DeepEvalProvider(EvalProvider):
    def __init__(self, provider: str, sampling_fraction: float = 1.0):
        super().__init__(provider, sampling_fraction)
        try:
            from deepeval import evaluate
            from deepeval.metrics import (
                AnswerRelevancyMetric,
                HallucinationMetric,
            )
            from deepeval.test_case import LLMTestCase

            self.deep_evaluate = evaluate
            self.AnswerRelevancyMetric = AnswerRelevancyMetric
            self.HallucinationMetric = HallucinationMetric
            self.LLMTestCase = LLMTestCase
        except ImportError:
            raise ImportError(
                "DeepEval is not installed. Please install it using `pip install deepeval`."
            )
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "Please set the `OPENAI_API_KEY` environment variable to run with DeepEval."
            )

    def _evaluate(
        self, query: str, context: str, completion: str
    ) -> dict[str, dict[str, str]]:
        test_case = self.LLMTestCase(
            input=query,
            actual_output=completion,
            context=[context],
            retrieval_context=[context],
        )
        # TODO - Make inner metrics configurable.

        answer_relevancy_metric = self.AnswerRelevancyMetric()
        hallucination_metric = self.HallucinationMetric()

        answer_relevancy_result = self.deep_evaluate(
            [test_case], [answer_relevancy_metric]
        )
        hallucination_result = self.deep_evaluate(
            [test_case], [hallucination_metric]
        )

        # TODO - Fix return type across evals, or at least locally.
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
