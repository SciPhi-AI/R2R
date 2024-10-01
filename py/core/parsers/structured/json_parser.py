# type: ignore
import json
from typing import Any, AsyncGenerator

from core.base.abstractions import DataType
from core.base.parsers.base_parser import AsyncParser


class JSONParser(AsyncParser[DataType]):
    """A parser for JSON data."""

    async def ingest(
        self, data: DataType, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """
        Ingest JSON data and yield a formatted text representation.

        :param data: The JSON data to parse.
        :param kwargs: Additional keyword arguments.
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        parsed_json = json.loads(data)
        formatted_text = self._parse_json(parsed_json)

        chunk_size = kwargs.get("chunk_size")
        if chunk_size and isinstance(chunk_size, int):
            # If chunk_size is provided and is an integer, yield the formatted text in chunks
            for i in range(0, len(formatted_text), chunk_size):
                yield formatted_text[i : i + chunk_size]
        else:
            # If no valid chunk_size is provided, yield the entire formatted text
            yield formatted_text

    def _parse_json(self, data: dict) -> str:
        def remove_objects_with_null(obj):
            if not isinstance(obj, dict):
                return obj
            result = obj.copy()
            for key, value in obj.items():
                if isinstance(value, dict):
                    result[key] = remove_objects_with_null(value)
                elif value is None:
                    del result[key]
            return result

        def format_json_as_text(obj, indent=0):
            lines = []
            indent_str = " " * indent

            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, (dict, list)):
                        nested = format_json_as_text(value, indent + 2)
                        lines.append(f"{indent_str}{key}:\n{nested}")
                    else:
                        lines.append(f"{indent_str}{key}: {value}")
            elif isinstance(obj, list):
                for item in obj:
                    nested = format_json_as_text(item, indent + 2)
                    lines.append(f"{nested}")
            else:
                return f"{indent_str}{obj}"

            return "\n".join(lines)

        return format_json_as_text(remove_objects_with_null(data))
