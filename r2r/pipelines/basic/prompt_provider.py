from typing import Any, Optional

from r2r.core import DefaultPromptProvider


class BasicPromptProvider(DefaultPromptProvider):
    BASIC_SYSTEM_PROMPT = "You are a helpful assistant."
    BASIC_TASK_PROMPT = """
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
        task_prompt: Optional[str] = None,
    ):
        super().__init__()
        self.add_prompt(
            "system_prompt", system_prompt or self.BASIC_SYSTEM_PROMPT
        )
        self.add_prompt("task_prompt", task_prompt or self.BASIC_TASK_PROMPT)

    def get_system_prompt(self, inputs: dict[str, Any]) -> str:
        return self.get_prompt("system_prompt", inputs)

    def get_task_prompt(self, inputs: dict[str, Any]) -> str:
        return self.get_prompt("task_prompt", inputs)
