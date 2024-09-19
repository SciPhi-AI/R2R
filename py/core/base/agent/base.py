from typing import Any, Callable, Dict, Optional, Union

from pydantic import BaseModel

from core.base.abstractions import MessageType

from ..abstractions.base import R2RSerializable


class Tool(R2RSerializable):
    name: str
    description: str
    results_function: Callable
    llm_format_function: Callable
    stream_function: Optional[Callable] = None
    parameters: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True


class ToolResult(R2RSerializable):
    raw_result: Any
    llm_formatted_result: str
    stream_result: Optional[str] = None


class Message(R2RSerializable):
    role: Union[MessageType, str]
    content: Optional[str] = None
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[list[Dict[str, Any]]] = None
