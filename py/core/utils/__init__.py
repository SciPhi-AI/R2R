import re
from typing import Set, Tuple

from shared.utils.base_utils import (
    SearchResultsCollector,
    SSEFormatter,
    convert_nonserializable_objects,
    deep_update,
    dump_collector,
    dump_obj,
    format_search_results_for_llm,
    generate_default_user_collection_id,
    generate_document_id,
    generate_extraction_id,
    generate_id,
    generate_user_id,
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

    Args:
        text: The text to search for citations. If None, returns an empty list.

    Returns:
        List of citation IDs matching the pattern [A-Za-z0-9]{7,8}
    """
    # Handle None or empty input
    if text is None or text == "":
        return []

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
        text: The text to search for citations. If None, returns an empty dict.

    Returns:
        Dictionary mapping citation IDs to lists of (start, end) position tuples,
        where start is the position of the opening bracket and end is the position
        just after the closing bracket.
    """
    # Handle None or empty input
    if text is None or text == "":
        return {}

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
    Tracks citation spans to ensure proper consolidation and deduplication.

    This class serves two purposes:
    1. Tracking which spans have already been processed to avoid duplicate emissions
    2. Maintaining a consolidated record of all citation spans for final answers

    The is_new_span method both checks if a span is new AND marks it as processed
    if it is new, which is important to understand when using this class.
    """

    def __init__(self):
        # Track which citation spans we've processed
        # Format: {citation_id: {(start, end), (start, end), ...}}
        self.processed_spans: dict[str, Set[Tuple[int, int]]] = {}

        # Track which citation IDs we've seen
        self.seen_citation_ids: Set[str] = set()

    def is_new_citation(self, citation_id: str) -> bool:
        """
        Check if this is the first occurrence of this citation ID.

        Args:
            citation_id: The citation ID to check

        Returns:
            True if this is the first time seeing this citation ID, False otherwise.
            Also adds the ID to seen_citation_ids if it's new.
        """
        if citation_id is None or citation_id == "":
            return False

        is_new = citation_id not in self.seen_citation_ids
        if is_new:
            self.seen_citation_ids.add(citation_id)
        return is_new

    def is_new_span(self, citation_id: str, span: Tuple[int, int]) -> bool:
        """
        Check if this span has already been processed for this citation ID.
        This method both checks if a span is new AND marks it as processed if it is new.

        Args:
            citation_id: The citation ID
            span: (start, end) position tuple

        Returns:
            True if this span hasn't been processed yet, False otherwise.
            Also adds the span to processed_spans if it's new.
        """
        # Handle invalid inputs
        if citation_id is None or citation_id == "" or span is None:
            return False

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
        """
        Get all processed spans for final answer consolidation.

        Returns:
            Dictionary mapping citation IDs to lists of their (start, end) spans.
        """
        return {
            cid: list(spans) for cid, spans in self.processed_spans.items()
        }

    def reset(self) -> None:
        """
        Reset the tracker to its initial empty state.
        Useful for testing or when reusing a tracker instance.
        """
        self.processed_spans.clear()
        self.seen_citation_ids.clear()


def find_new_citation_spans(
    text: str, tracker: CitationTracker
) -> dict[str, list[Tuple[int, int]]]:
    """
    Extract citation spans that haven't been processed yet.

    Args:
        text: Text to search. If None, returns an empty dict.
        tracker: The CitationTracker instance to check against for new spans

    Returns:
        Dictionary of citation IDs to lists of new (start, end) spans
        that haven't been processed by the tracker yet.
    """
    # Handle None or empty input
    if text is None or text == "":
        return {}

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
