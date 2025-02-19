# type: ignore
from typing import IO, AsyncGenerator, Optional

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class CSVParser(AsyncParser[str | bytes]):
    """A parser for CSV data."""

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
        """Ingest CSV data and yield text from each row."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        csv_reader = self.csv.reader(self.StringIO(data))
        for row in csv_reader:
            yield ", ".join(row)


class CSVParserAdvanced(AsyncParser[str | bytes]):
    """A parser for CSV data."""

    def __init__(
        self, config: IngestionConfig, llm_provider: CompletionProvider
    ):
        self.llm_provider = llm_provider
        self.config = config

        import csv
        from io import StringIO

        self.csv = csv
        self.StringIO = StringIO

    def get_delimiter(
        self, file_path: Optional[str] = None, file: Optional[IO[bytes]] = None
    ):
        sniffer = self.csv.Sniffer()
        num_bytes = 65536

        if file:
            lines = file.readlines(num_bytes)
            file.seek(0)
            data = "\n".join(ln.decode("utf-8") for ln in lines)
        elif file_path is not None:
            with open(file_path) as f:
                data = "\n".join(f.readlines(num_bytes))

        return sniffer.sniff(data, delimiters=",;").delimiter

    async def ingest(
        self,
        data: str | bytes,
        num_col_times_num_rows: int = 100,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Ingest CSV data and yield text from each row."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        # let the first row be the header
        delimiter = self.get_delimiter(file=self.StringIO(data))

        csv_reader = self.csv.reader(self.StringIO(data), delimiter=delimiter)

        header = next(csv_reader)
        num_cols = len(header.split(delimiter))
        num_rows = num_col_times_num_rows // num_cols

        chunk_rows = []
        for row_num, row in enumerate(csv_reader):
            chunk_rows.append(row)
            if row_num % num_rows == 0:
                yield (
                    ", ".join(header)
                    + "\n"
                    + "\n".join([", ".join(row) for row in chunk_rows])
                )
                chunk_rows = []

        if chunk_rows:
            yield (
                ", ".join(header)
                + "\n"
                + "\n".join([", ".join(row) for row in chunk_rows])
            )
