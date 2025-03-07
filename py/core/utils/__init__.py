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

SHORT_ID_PATTERN = re.compile(r"[A-Za-z0-9]{7,8}")


def extract_citations(text: str) -> list[str]:
    """
    Example: parse out bracket references containing short IDs like [abc1234].
    Return a list of Citation objects (with .index = ???).
    """
    # This is up to you how you store them in the Citation model.
    # For example:
    sids = []
    BRACKET_PATTERN = re.compile(r"\[([^\]]+)\]")
    bracket_id_counter = 0

    for match in BRACKET_PATTERN.finditer(text):
        bracket_text = match.group(1)

        found_ids = SHORT_ID_PATTERN.findall(bracket_text)
        if not found_ids:
            continue

        # For each short ID, create a Citation. If you want each ID in separate bracket objects:
        for sid in found_ids:
            bracket_id_counter += 1
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
