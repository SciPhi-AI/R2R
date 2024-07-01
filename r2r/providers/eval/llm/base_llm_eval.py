from fractions import Fraction
from typing import Union

from r2r import EvalConfig, EvalProvider, LLMProvider, PromptProvider
from r2r.base.abstractions.llm import GenerationConfig


class LLMEvalProvider(EvalProvider):
    def __init__(
        self,
        config: EvalConfig,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
    ):
        super().__init__(config)

        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider

    def _calc_query_context_relevancy(self, query: str, context: str) -> float:
        system_prompt = self.prompt_provider.get_prompt("default_system")
        eval_prompt = self.prompt_provider.get_prompt(
            "rag_context_eval", {"query": query, "context": context}
        )
        response = self.llm_provider.get_completion(
            self.prompt_provider._get_message_payload(
                system_prompt, eval_prompt
            ),
            self.eval_generation_config,
        )
        response_text = response.choices[0].message.content
        fraction = (
            response_text
            # Get the fraction in the returned tuple
            .split(",")[-1][:-1]
            # Remove any quotes and spaces
            .replace("'", "")
            .replace('"', "")
            .strip()
        )
        return float(Fraction(fraction))

    def _calc_answer_grounding(
        self, query: str, context: str, answer: str
    ) -> float:
        system_prompt = self.prompt_provider.get_prompt("default_system")
        eval_prompt = self.prompt_provider.get_prompt(
            "rag_answer_eval",
            {"query": query, "context": context, "answer": answer},
        )
        response = self.llm_provider.get_completion(
            self.prompt_provider._get_message_payload(
                system_prompt, eval_prompt
            ),
            self.eval_generation_config,
        )
        response_text = response.choices[0].message.content
        fraction = (
            response_text
            # Get the fraction in the returned tuple
            .split(",")[-1][:-1]
            # Remove any quotes and spaces
            .replace("'", "")
            .replace('"', "")
            .strip()
        )
        return float(Fraction(fraction))

    def _evaluate(
        self,
        query: str,
        context: str,
        answer: str,
        eval_generation_config: GenerationConfig,
    ) -> dict[str, dict[str, Union[str, float]]]:
        self.eval_generation_config = eval_generation_config
        query_context_relevancy = self._calc_query_context_relevancy(
            query, context
        )
        answer_grounding = self._calc_answer_grounding(query, context, answer)
        return {
            "query_context_relevancy": query_context_relevancy,
            "answer_grounding": answer_grounding,
        }
