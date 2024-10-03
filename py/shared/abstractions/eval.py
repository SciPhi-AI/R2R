from typing import Optional

from .base import R2RSerializable


class RagEvalLLMResponse(R2RSerializable):
    """Responses from LLMs for a single question."""

    question: str
    reference_answer: str
    generated_answer: str
    llm_judgement: str
    is_correct: bool


class RagEvalResultMetrics(R2RSerializable):
    """Metrics of RAG evaluation."""

    total_questions: int
    correct_answers: int
    incorrect_answers: int
    accuracy: float
    f1_score: float
    precision: float
    recall: float

class RagEvalResult(R2RSerializable):
    """Result of RAG evaluation."""

    metrics: RagEvalResultMetrics
    llm_responses: list[RagEvalLLMResponse]


class RagEvalQuestion(R2RSerializable):
    """A question in RAG evaluation."""

    question: str
    reference_answer: str
    context: Optional[str] = None # not used now
    