import re
from typing import Any, Dict, Generator, Iterable, Optional, Tuple

from flupy import flu

from .base import AdapterContext, AdapterStep


class MarkdownChunker(AdapterStep):
    """
    MarkdownChunker is an AdapterStep that splits a markdown string into chunks where a heading signifies the start of a chunk, and yields each chunk as a separate record.
    """

    def __init__(self, *, skip_during_query: bool):
        """
        Initializes the MarkdownChunker adapter.

        Args:
            skip_during_query (bool): Whether to skip chunking during querying.
        """
        self.skip_during_query = skip_during_query

    @staticmethod
    def split_by_heading(
        md: str, max_tokens: int
    ) -> Generator[str, None, None]:
        regex_split = r"^(#{1,6}\s+.+)$"
        headings = [
            match.span()[0]
            for match in re.finditer(regex_split, md, flags=re.MULTILINE)
        ]

        if headings == [] or headings[0] != 0:
            headings.insert(0, 0)

        sections = [md[i:j] for i, j in zip(headings, headings[1:] + [None])]

        for section in sections:
            chunks = flu(section.split(" ")).chunk(max_tokens)

            is_not_useless_chunk = lambda i: not i in ["", "\n", []]

            joined_chunks = filter(
                is_not_useless_chunk, [" ".join(chunk) for chunk in chunks]
            )

            for joined_chunk in joined_chunks:
                yield joined_chunk

    def __call__(
        self,
        records: Iterable[Tuple[str, Any, Optional[Dict]]],
        adapter_context: AdapterContext,
        max_tokens: int = 99999999,
    ) -> Generator[Tuple[str, Any, Dict], None, None]:
        """
        Splits each markdown string in the records into chunks where each heading starts a new chunk, and yields each chunk
        as a separate record. If the `skip_during_query` attribute is set to True,
        this step is skipped during querying.

        Args:
            records (Iterable[Tuple[str, Any, Optional[Dict]]]): Iterable of tuples each containing an id, a markdown string and an optional dict.
            adapter_context (AdapterContext): Context of the adapter.
            max_tokens (int): The maximum number of tokens per chunk

        Yields:
            Tuple[str, Any, Dict]: The id appended with chunk index, the chunk, and the metadata.
        """
        if max_tokens and max_tokens < 1:
            raise ValueError("max_tokens must be a nonzero positive integer")

        if (
            adapter_context == AdapterContext("query")
            and self.skip_during_query
        ):
            for id, markdown, metadata in records:
                yield (id, markdown, metadata or {})
        else:
            for id, markdown, metadata in records:
                headings = MarkdownChunker.split_by_heading(
                    markdown, max_tokens
                )
                for heading_ix, heading in enumerate(headings):
                    yield (
                        f"{id}_head_{str(heading_ix).zfill(3)}",
                        heading,
                        metadata or {},
                    )
