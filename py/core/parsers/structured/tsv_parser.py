# type: ignore
from typing import IO, AsyncGenerator

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class TSVParser(AsyncParser[str | bytes]):
    """A parser for TSV (Tab Separated Values) data."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config

        import csv
        from io import StringIO

        self.csv = csv
        self.StringIO = StringIO

    async def ingest(
        self, data: str | bytes, *args, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest TSV data and yield text from each row."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        tsv_reader = self.csv.reader(self.StringIO(data), delimiter="\t")
        for row in tsv_reader:
            yield ", ".join(row)  # Still join with comma for readability


class TSVParserAdvanced(AsyncParser[str | bytes]):
    """An advanced parser for TSV data with chunking support."""

    def __init__(
        self, config: IngestionConfig, llm_provider: CompletionProvider
    ):
        self.llm_provider = llm_provider
        self.config = config

        import csv
        from io import StringIO

        self.csv = csv
        self.StringIO = StringIO

    def validate_tsv(self, file: IO[bytes]) -> bool:
        """Validate if the file is actually tab-delimited."""
        num_bytes = 65536
        lines = file.readlines(num_bytes)
        file.seek(0)

        if not lines:
            return False

        # Check if tabs exist in first few lines
        sample = "\n".join(ln.decode("utf-8") for ln in lines[:5])
        return "\t" in sample

    async def ingest(
        self,
        data: str | bytes,
        num_col_times_num_rows: int = 100,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Ingest TSV data and yield text in chunks."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        # Validate TSV format
        if not self.validate_tsv(self.StringIO(data)):
            raise ValueError("File does not appear to be tab-delimited")

        tsv_reader = self.csv.reader(self.StringIO(data), delimiter="\t")

        # Get header
        header = next(tsv_reader)
        num_cols = len(header)
        num_rows = num_col_times_num_rows // num_cols

        chunk_rows = []
        for row_num, row in enumerate(tsv_reader):
            chunk_rows.append(row)
            if row_num % num_rows == 0:
                yield (
                    ", ".join(header)
                    + "\n"
                    + "\n".join([", ".join(row) for row in chunk_rows])
                )
                chunk_rows = []

        # Yield remaining rows
        if chunk_rows:
            yield (
                ", ".join(header)
                + "\n"
                + "\n".join([", ".join(row) for row in chunk_rows])
            )
