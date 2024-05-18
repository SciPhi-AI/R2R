from fractions import Fraction
from typing import Union, Optional

from r2r import (
    EvalConfig,
    EvalProvider,
    LLMProvider,
    PromptProvider,
    GenerationConfig,
)


class LocalEvalProvider(EvalProvider):
    def __init__(
        self,
        config: EvalConfig,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        model: Optional[str] = None,
        generation_config: Optional[GenerationConfig] = None,
    ):
        super().__init__(config)
        if model and generation_config:
            raise ValueError(
                "Cannot provide both `model` and `generation_config`."
            )

        if not model:
            model = "gpt-4o"

        if not generation_config:
            generation_config = GenerationConfig(model=model)

        self.generation_config = generation_config

        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider

    def _calc_query_context_relevancy(self, query: str, context: str) -> float:
        system_prompt = self.prompt_provider.get_prompt(
            "default_system"
        )
        eval_prompt = self.prompt_provider.get_prompt(
            "rag_context_eval", {"query": query, "context": context}
        )
        response = self.llm_provider.get_completion(
            self.prompt_provider._get_message_payload(
                system_prompt, eval_prompt
            ),
            self.generation_config,
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


    def _calc_answer_grounding(self, query: str, context: str, answer: str) -> float:
        system_prompt = self.prompt_provider.get_prompt(
            "default_system"
        )
        eval_prompt = self.prompt_provider.get_prompt(
            "rag_answer_eval", {"query": query, "context": context, "answer": answer}
        )
        response = self.llm_provider.get_completion(
            self.prompt_provider._get_message_payload(
                system_prompt, eval_prompt
            ),
            self.generation_config,
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
        self, query: str, context: str, answer: str
    ) -> dict[str, dict[str, Union[str, float]]]:
        query_context_relevancy = self._calc_query_context_relevancy(
            query, context
        )
        answer_grounding = self._calc_answer_grounding(
            query, context, answer
        )
        return {
            "query_context_relevancy": query_context_relevancy,
            "answer_grounding": answer_grounding,
        }

    def sent_tokenize(self, text: str) -> list[str]:
        """Split into sentences"""
        sentences = self.seg.segment(text)
        assert isinstance(sentences, list)
        return sentences
