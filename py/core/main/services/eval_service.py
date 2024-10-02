from typing import Optional
from uuid import UUID

from core.base import RunType, VectorSearchSettings, KGSearchSettings, GenerationConfig
from core.base.providers import OrchestrationProvider
from core.base.services import Service

class EvalService(Service):
    def __init__(
        self,
        providers,
        run_type: RunType = RunType.EVALUATION,
        orchestration_provider: Optional[OrchestrationProvider] = None,
    ):
        super().__init__(providers, run_type, orchestration_provider)

    async def run_evaluation(self, eval_config: dict, user_id: UUID) -> dict:
        question = eval_config['question']
        reference_answer = eval_config['reference_answer']

        # Run RAG query
        rag_response = await self.providers.retrieval.rag(
            query=question,
            vector_search_settings=VectorSearchSettings(),
            kg_search_settings=KGSearchSettings(),
            rag_generation_config=GenerationConfig(),
        )

        llm_answer = rag_response['answer']

        # Compare LLM answer with reference answer
        comparison_prompt = f"""
        Question: {question}

        Reference Answer: {reference_answer}

        LLM Answer: {llm_answer}

        Please evaluate the LLM Answer compared to the Reference Answer. Consider the following:
        1. Accuracy: How factually correct is the LLM Answer?
        2. Completeness: Does the LLM Answer cover all key points from the Reference Answer?
        3. Relevance: How well does the LLM Answer address the original question?

        Provide a score from 0 to 10 for each aspect, where 0 is the lowest and 10 is the highest.
        Then, give an overall score and a brief explanation of your evaluation.

        Format your response as follows:
        Accuracy: [score]
        Completeness: [score]
        Relevance: [score]
        Overall Score: [score]
        Explanation: [Your explanation here]
        """

        comparison_response = await self.providers.completions.complete(
            prompt=comparison_prompt,
            generation_config=GenerationConfig(max_tokens=300),
        )

        return {
            "question": question,
            "reference_answer": reference_answer,
            "llm_answer": llm_answer,
            "evaluation": comparison_response['text'],
        }
