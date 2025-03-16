import re
from typing import Set, Tuple

from shared.utils.base_utils import (
    SearchResultsCollector,
    SSEFormatter,
    convert_nonserializable_objects,
    decrement_version,
    deep_update,
    dump_collector,
    dump_obj,
    format_search_results_for_llm,
    generate_default_user_collection_id,
    generate_document_id,
    generate_extraction_id,
    generate_id,
    generate_user_id,
    increment_version,
    num_tokens,
    num_tokens_from_messages,
    update_settings_from_dict,
    validate_uuid,
    yield_sse_event,
)
from shared.utils.splitter.text import (
    RecursiveCharacterTextSplitter,
    TextSplitter,
)


def extract_citations(text: str) -> list[str]:
    """
    Extract citation IDs enclosed in brackets like [abc1234].
    Returns a list of citation IDs.
    """
    # Direct pattern to match IDs inside brackets with alphanumeric pattern
    CITATION_PATTERN = re.compile(r"\[([A-Za-z0-9]{7,8})\]")

    sids = []
    for match in CITATION_PATTERN.finditer(text):
        sid = match.group(1)
        sids.append(sid)

    return sids


def extract_citation_spans(text: str) -> dict[str, list[Tuple[int, int]]]:
    """
    Extract citation IDs with their positions in the text.

    Args:
        text: The text to search for citations

    Returns:
        dictionary mapping citation IDs to lists of (start, end) position tuples
    """
    # Use the same pattern as the original extract_citations
    CITATION_PATTERN = re.compile(r"\[([A-Za-z0-9]{7,8})\]")

    citation_spans: dict = {}

    for match in CITATION_PATTERN.finditer(text):
        sid = match.group(1)
        start = match.start()
        end = match.end()

        if sid not in citation_spans:
            citation_spans[sid] = []

        # Add the position span
        citation_spans[sid].append((start, end))

    return citation_spans


class CitationTracker:
    """
    Tracks citation spans to ensure each one is only emitted once.
    """

    def __init__(self):
        # Track which citation spans we've processed
        # Format: {citation_id: {(start, end), (start, end), ...}}
        self.processed_spans: dict[str, Set[Tuple[int, int]]] = {}

        # Track which citation IDs we've seen
        self.seen_citation_ids: Set[str] = set()

    def is_new_citation(self, citation_id: str) -> bool:
        """Check if this is the first occurrence of this citation ID."""
        is_new = citation_id not in self.seen_citation_ids
        if is_new:
            self.seen_citation_ids.add(citation_id)
        return is_new

    def is_new_span(self, citation_id: str, span: Tuple[int, int]) -> bool:
        """
        Check if this span has already been processed for this citation ID.

        Args:
            citation_id: The citation ID
            span: (start, end) position tuple

        Returns:
            True if this span hasn't been processed yet, False otherwise
        """
        # Initialize set for this citation ID if needed
        if citation_id not in self.processed_spans:
            self.processed_spans[citation_id] = set()

        # Check if we've seen this span before
        if span in self.processed_spans[citation_id]:
            return False

        # This is a new span, track it
        self.processed_spans[citation_id].add(span)
        return True

    def get_all_spans(self) -> dict[str, list[Tuple[int, int]]]:
        """Get all processed spans for final answer."""
        return {
            cid: list(spans) for cid, spans in self.processed_spans.items()
        }


def find_new_citation_spans(
    text: str, tracker: CitationTracker
) -> dict[str, list[Tuple[int, int]]]:
    """
    Extract citation spans that haven't been processed yet.

    Args:
        text: Text to search
        tracker: The CitationTracker instance

    Returns:
        dictionary of citation IDs to lists of new (start, end) spans
    """
    # Get all citation spans in the text
    all_spans = extract_citation_spans(text)

    # Filter to only spans we haven't processed yet
    new_spans: dict = {}

    for cid, spans in all_spans.items():
        for span in spans:
            if tracker.is_new_span(cid, span):
                if cid not in new_spans:
                    new_spans[cid] = []
                new_spans[cid].append(span)

    return new_spans


__all__ = [
    "format_search_results_for_llm",
    "generate_id",
    "generate_document_id",
    "generate_extraction_id",
    "generate_user_id",
    "increment_version",
    "decrement_version",
    "generate_default_user_collection_id",
    "validate_uuid",
    "yield_sse_event",
    "dump_collector",
    "dump_obj",
    "convert_nonserializable_objects",
    "num_tokens",
    "num_tokens_from_messages",
    "SSEFormatter",
    "SearchResultsCollector",
    "update_settings_from_dict",
    "deep_update",
    # Text splitter
    "RecursiveCharacterTextSplitter",
    "TextSplitter",
    "extract_citations",
    "extract_citation_spans",
    "CitationTracker",
    "find_new_citation_spans",
]
