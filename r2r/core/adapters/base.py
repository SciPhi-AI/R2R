import json
import string
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any, Generic, TypeVar, Union

from bs4 import BeautifulSoup

T = TypeVar("T")


class Adapter(ABC, Generic[T]):
    @abstractmethod
    def adapt(self, data: Any) -> T:
        pass


class TextAdapter(Adapter[str]):
    def adapt(self, data: str) -> list[str]:
        return [data]


class JSONAdapter(Adapter[str]):
    def adapt(self, data: Union[str, bytes]) -> list[str]:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return [self._parse_json(json.loads(data))]

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


class HTMLAdapter(Adapter[str]):
    def adapt(self, data: str) -> list[str]:
        soup = BeautifulSoup(data, "html.parser")
        return [soup.get_text()]


class PDFAdapter(Adapter[str]):
    def __init__(self):
        try:
            from pypdf import PdfReader

            self.PdfReader = PdfReader
        except ImportError:
            raise ValueError(
                "Error, `pypdf` is required to run `PyPDFAdapter`. Please install it using `pip install pypdf`."
            )

    def adapt(self, data: bytes) -> list[str]:
        pdf = self.PdfReader(BytesIO(data))
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text is not None:
                page_text = "".join(
                    filter(lambda x: x in string.printable, page_text)
                )
                text += page_text
        return [text]
