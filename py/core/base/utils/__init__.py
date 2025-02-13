import json
import re
import uuid
from datetime import datetime

from shared.utils import (
    RecursiveCharacterTextSplitter,
    TextSplitter,
    _decorate_vector_type,
    _get_vector_column_str,
    decrement_version,
    deep_update,
    extract_citations,
    format_search_results_for_llm,
    generate_default_prompt_id,
    generate_default_user_collection_id,
    generate_document_id,
    generate_entity_document_id,
    generate_extraction_id,
    generate_id,
    generate_user_id,
    increment_version,
    map_citations_to_collector,
    reassign_citations_in_order,
    validate_uuid,
)


class CitationRelabeler:
    """
    Dynamically assign ascending newIndex values (1,2,3,...) to
    any previously unseen bracket oldRef (e.g. [12] -> [1], [12] -> [1], [2], etc.).
    """

    def __init__(self):
        self._oldref_to_newref = {}  # map oldRef -> newRef
        self._next_new_ref = 1

    def get_or_assign_newref(self, old_ref: int) -> int:
        """
        Return the stable newRef assigned to `old_ref`.
        If we haven't seen `old_ref` before, assign the next available new index.
        """
        if old_ref not in self._oldref_to_newref:
            self._oldref_to_newref[old_ref] = self._next_new_ref
            self._next_new_ref += 1
        return self._oldref_to_newref[old_ref]

    def rewrite_with_newrefs(self, text: str) -> str:
        """
        Takes raw text (which may have brackets [ 3], [2], etc.) and
        rewrites them into their newly assigned references [1], [2], ...

        - If an oldRef is known, replace it with the correct newRef
        - If it's unknown, assign a newRef and then replace
        """
        bracket_pattern = re.compile(r"\[\s*(\d+)\s*\]")

        def _replace(match):
            old_str = match.group(1)  # "3" or " 2"
            old_int = int(old_str)
            new_ref = self.get_or_assign_newref(old_int)
            return f"[{new_ref}]"

        return bracket_pattern.sub(_replace, text)

    def finalize_all_citations(self, text: str):
        """
        If you need to do a final pass at the very end, you can re-check
        all the brackets to ensure they are correctly assigned. For text that
        has placeholders or repeated references, it ensures they're correct.
        """
        return self.rewrite_with_newrefs(text)

    def get_mapping(self) -> dict[int, int]:
        """
        Returns the old->new mapping dict for downstream usage.
        """
        return dict(self._oldref_to_newref)


async def yield_sse_event(event_name: str, payload: dict, chunk_size=1024):
    """
    Helper that yields a single SSE event in properly chunked lines.

    e.g. event: event_name
         data: (partial JSON 1)
         data: (partial JSON 2)
         ...
         [blank line to end event]
    """

    # SSE: first the "event: ..."
    yield f"event: {event_name}\n"

    # Convert payload to JSON
    content_str = json.dumps(payload, default=str)

    # data
    yield f"data: {content_str}\n"

    # blank line signals end of SSE event
    yield "\n"


__all__ = [
    "format_search_results_for_llm",
    "generate_id",
    "generate_default_user_collection_id",
    "increment_version",
    "decrement_version",
    "generate_document_id",
    "generate_extraction_id",
    "generate_user_id",
    "generate_entity_document_id",
    "generate_default_prompt_id",
    "RecursiveCharacterTextSplitter",
    "TextSplitter",
    "validate_uuid",
    "deep_update",
    "map_citations_to_collector",
    "extract_citations",
    "reassign_citations_in_order",
    "_decorate_vector_type",
    "_get_vector_column_str",
    "yield_sse_event",
    "CitationRelabeler",
]


def convert_nonserializable_objects(obj):
    if isinstance(obj, dict):
        new_obj = {}
        for key, value in obj.items():
            # Convert key to string if it is a UUID or not already a string.
            new_key = str(key) if not isinstance(key, str) else key
            new_obj[new_key] = convert_nonserializable_objects(value)
        return new_obj
    elif isinstance(obj, list):
        return [convert_nonserializable_objects(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_nonserializable_objects(item) for item in obj)
    elif isinstance(obj, set):
        return {convert_nonserializable_objects(item) for item in obj}
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()  # Convert datetime to ISO formatted string
    else:
        return obj
