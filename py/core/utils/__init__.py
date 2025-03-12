import re

from shared.utils.base_utils import (
    SearchResultsCollector,
    SSEFormatter,
    convert_nonserializable_objects,
    decrement_version,
    deep_update,
    dump_collector,
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
]
