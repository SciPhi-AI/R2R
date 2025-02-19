# type: ignore
import asyncio
import json
from typing import AsyncGenerator

from core.base import R2RException
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class JSONParser(AsyncParser[str | bytes]):
    """A parser for JSON data."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config

    async def ingest(
        self, data: str | bytes, *args, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest JSON data and yield a formatted text representation.

        :param data: The JSON data to parse.
        :param kwargs: Additional keyword arguments.
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        loop = asyncio.get_event_loop()

        try:
            parsed_json = await loop.run_in_executor(None, json.loads, data)
            formatted_text = await loop.run_in_executor(
                None, self._parse_json, parsed_json
            )
        except json.JSONDecodeError as e:
            raise R2RException(
                message=f"Failed to parse JSON data, likely due to invalid JSON: {str(e)}",
                status_code=400,
            ) from e

        chunk_size = kwargs.get("chunk_size")
        if chunk_size and isinstance(chunk_size, int):
            # If chunk_size is provided and is an integer, yield the formatted text in chunks
            for i in range(0, len(formatted_text), chunk_size):
                yield formatted_text[i : i + chunk_size]
                await asyncio.sleep(0)
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
