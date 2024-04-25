from typing import Any, Optional

from r2r.core.providers.prompt import PromptProvider


class BasicPromptProvider(PromptProvider):
    BASIC_SYSTEM_PROMPT = "You are a helpful assistant."
    BASIC_RETURN_PROMPT = """
    ## Task:
    Answer the query given immediately below given the context which follows later.

    ### Query:
    {query}

    ### Context:
    {context}

    ### Query:
    {query}

    ## Response:
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        return_pompt: Optional[str] = None,
    ):
        self.prompts: dict[str, str] = {}
        self.add_prompt(
            "system_prompt", system_prompt or self.BASIC_SYSTEM_PROMPT
        )
        self.add_prompt(
            "return_pompt", return_pompt or self.BASIC_RETURN_PROMPT
        )

    def add_prompt(self, prompt_name: str, prompt: str) -> None:
        self.prompts[prompt_name] = prompt

    def get_prompt(
        self, prompt_name: str, inputs: Optional[dict[str, Any]] = None
    ) -> str:
        prompt = self.prompts.get(prompt_name)
        if prompt is None:
            raise ValueError(f"Prompt '{prompt_name}' not found.")
        return prompt.format(**(inputs or {}))

    def get_all_prompts(self) -> dict[str, str]:
        return self.prompts.copy()

    def get_system_prompt(self, inputs: dict[str, Any]) -> str:
        return self.get_prompt("system_prompt", inputs)

    def get_return_prompt(self, inputs: dict[str, Any]) -> str:
        return self.get_prompt("return_pompt", inputs)
