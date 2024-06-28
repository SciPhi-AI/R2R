from io import BytesIO
from typing import AsyncGenerator

from r2r.base.abstractions.document import DataType
from r2r.base.parsers.base_parser import AsyncParser


class XLSXParser(AsyncParser[DataType]):
    """A parser for XLSX data."""

    def __init__(self):
        try:
            from openpyxl import load_workbook

            self.load_workbook = load_workbook
        except ImportError:
            raise ValueError(
                "Error, `openpyxl` is required to run `XLSXParser`. Please install it using `pip install openpyxl`."
            )

    async def ingest(self, data: bytes) -> AsyncGenerator[str, None]:
        """Ingest XLSX data and yield text from each row."""
        if isinstance(data, str):
            raise ValueError("XLSX data must be in bytes format.")

        wb = self.load_workbook(filename=BytesIO(data))
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                yield ", ".join(map(str, row))
