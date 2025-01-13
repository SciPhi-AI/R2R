from typing import Any, Callable, Optional

from ..abstractions import FUSESerializable


class Tool(FUSESerializable):
    name: str
    description: str
    results_function: Callable
    llm_format_function: Callable
    stream_function: Optional[Callable] = None
    parameters: Optional[dict[str, Any]] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class ToolResult(FUSESerializable):
    raw_result: Any
    llm_formatted_result: str
    stream_result: Optional[str] = None
