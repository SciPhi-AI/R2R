from datasets import Dataset
from typing import Union, Optional
from uuid import UUID
from .models import RagEvalResult
from shared.abstractions.eval import EvalConfig, RagEvalQuestion

class EvalMethods:

    @staticmethod
    async def evaluate_rag(client, 
        dataset: list[RagEvalQuestion], 
        collection_id: Optional[UUID] = None, 
        eval_config: Optional[EvalConfig] = None
        ) -> RagEvalResult:
        """
        Evaluate RAG performance for a given collection and dataset.
        """

        client.add_prompt(eval_config.rag_prompt.name, eval_config.rag_prompt.template, eval_config.rag_prompt.input_types)
        client.add_prompt(eval_config.llm_judgement_prompt.name, eval_config.llm_judgement_prompt.template, eval_config.llm_judgement_prompt.input_types)

        for question in dataset:
            data = {"dataset": dataset}
            if collection_id is not None:
                data["collection_id"] = collection_id

            rag_response = client.rag(
                query=question.question,
                vector_search_settings=eval_config.vector_search_settings,
                kg_search_settings=eval_config.kg_search_settings,
                rag_generation_config=eval_config.rag_generation_config,
            )

            # Run RAG query
            # Compare LLM answer with reference answer
            comparison_prompt = f"""
                Question: {question.question}
                Reference Answer: {question.reference_answer}
                LLM Answer: {rag_response['answer']}
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

            comparison_response = await client.completions.complete(
                prompt=comparison_prompt,
                generation_config=eval_config.rag_generation_config,
            )

        return {
            "question": question,
            "reference_answer": reference_answer,
            "llm_answer": llm_answer,
            "evaluation": comparison_response['text'],
        }