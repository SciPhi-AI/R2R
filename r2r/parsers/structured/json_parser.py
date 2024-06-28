import json
from typing import AsyncGenerator

from r2r.base.abstractions.document import DataType
from r2r.base.parsers.base_parser import AsyncParser


class JSONParser(AsyncParser[DataType]):
    """A parser for JSON data."""

    async def ingest(self, data: DataType) -> AsyncGenerator[str, None]:
        """Ingest JSON data and yield a formatted text representation."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        yield self._parse_json(json.loads(data))

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
