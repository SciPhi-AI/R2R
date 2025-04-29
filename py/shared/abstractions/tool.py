from typing import Any, Callable, Optional

from ..abstractions import R2RSerializable


class Tool(R2RSerializable):
    name: str
    description: str
    results_function: Callable
    llm_format_function: Optional[Callable] = None
    stream_function: Optional[Callable] = None
    parameters: Optional[dict[str, Any]] = None
    context: Optional[Any] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def set_context(self, context: Any) -> None:
        """Set the context for this tool."""
        self.context = context

    async def execute(self, *args, **kwargs):
        """
        Execute the tool with context awareness.
        This wraps the results_function to ensure context is available.
        """
        if self.context is None:
            raise ValueError(
                f"Tool '{self.name}' requires context but none was provided"
            )

        # Call the actual implementation with context
        return await self.results_function(context=self.context, **kwargs)


class ToolResult(R2RSerializable):
    raw_result: Any
    llm_formatted_result: str
    stream_result: Optional[str] = None
