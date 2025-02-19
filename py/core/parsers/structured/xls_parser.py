# type: ignore
from typing import AsyncGenerator

import networkx as nx
import numpy as np
import xlrd

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class XLSParser(AsyncParser[str | bytes]):
    """A parser for XLS (Excel 97-2003) data."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.xlrd = xlrd

    async def ingest(
        self, data: bytes, *args, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest XLS data and yield text from each row."""
        if isinstance(data, str):
            raise ValueError("XLS data must be in bytes format.")

        wb = self.xlrd.open_workbook(file_contents=data)
        for sheet in wb.sheets():
            for row_idx in range(sheet.nrows):
                # Get all values in the row
                row_values = []
                for col_idx in range(sheet.ncols):
                    cell = sheet.cell(row_idx, col_idx)
                    # Handle different cell types
                    if cell.ctype == self.xlrd.XL_CELL_DATE:
                        try:
                            value = self.xlrd.xldate_as_datetime(
                                cell.value, wb.datemode
                            ).strftime("%Y-%m-%d")
                        except Exception:
                            value = str(cell.value)
                    elif cell.ctype == self.xlrd.XL_CELL_BOOLEAN:
                        value = str(bool(cell.value)).lower()
                    elif cell.ctype == self.xlrd.XL_CELL_ERROR:
                        value = "#ERROR#"
                    else:
                        value = str(cell.value).strip()

                    row_values.append(value)

                # Yield non-empty rows
                if any(val.strip() for val in row_values):
                    yield ", ".join(row_values)


class XLSParserAdvanced(AsyncParser[str | bytes]):
    """An advanced parser for XLS data with chunking support."""

    def __init__(
        self, config: IngestionConfig, llm_provider: CompletionProvider
    ):
        self.llm_provider = llm_provider
        self.config = config
        self.nx = nx
        self.np = np
        self.xlrd = xlrd

    def connected_components(self, arr):
        g = self.nx.grid_2d_graph(len(arr), len(arr[0]))
        empty_cell_indices = list(zip(*self.np.where(arr == ""), strict=False))
        g.remove_nodes_from(empty_cell_indices)
        components = self.nx.connected_components(g)
        for component in components:
            rows, cols = zip(*component, strict=False)
            min_row, max_row = min(rows), max(rows)
            min_col, max_col = min(cols), max(cols)
            yield arr[min_row : max_row + 1, min_col : max_col + 1]

    def get_cell_value(self, cell, workbook):
        """Extract cell value handling different data types."""
        if cell.ctype == self.xlrd.XL_CELL_DATE:
            try:
                return self.xlrd.xldate_as_datetime(
                    cell.value, workbook.datemode
                ).strftime("%Y-%m-%d")
            except Exception:
                return str(cell.value)
        elif cell.ctype == self.xlrd.XL_CELL_BOOLEAN:
            return str(bool(cell.value)).lower()
        elif cell.ctype == self.xlrd.XL_CELL_ERROR:
            return "#ERROR#"
        else:
            return str(cell.value).strip()

    async def ingest(
        self, data: bytes, num_col_times_num_rows: int = 100, *args, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest XLS data and yield text from each connected component."""
        if isinstance(data, str):
            raise ValueError("XLS data must be in bytes format.")

        workbook = self.xlrd.open_workbook(file_contents=data)

        for sheet in workbook.sheets():
            # Convert sheet to numpy array with proper value handling
            ws_data = self.np.array(
                [
                    [
                        self.get_cell_value(sheet.cell(row, col), workbook)
                        for col in range(sheet.ncols)
                    ]
                    for row in range(sheet.nrows)
                ]
            )

            for table in self.connected_components(ws_data):
                if len(table) <= 1:
                    continue

                num_rows = len(table)
                num_rows_per_chunk = num_col_times_num_rows // num_rows
                headers = ", ".join(table[0])

                for i in range(1, num_rows, num_rows_per_chunk):
                    chunk = table[i : i + num_rows_per_chunk]
                    yield (
                        headers
                        + "\n"
                        + "\n".join([", ".join(row) for row in chunk])
                    )
