"""Interface for tools."""
from typing import Awaitable, Callable, Dict, Optional

from pydantic import BaseModel, Extra


class Tool(BaseModel):
    """`Tool` exposes a function or coroutine directly."""

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True

    function: Callable[..., str]
    name: str = ""
    description: str = ""
    coroutine: Optional[Callable[..., Awaitable[str]]] = None

    def run(self, tool_input: Dict[str, str]) -> str:
        return self.function(**tool_input)
