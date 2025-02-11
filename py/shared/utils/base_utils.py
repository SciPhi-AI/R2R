import json
import logging
import math
import re
from copy import deepcopy
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Iterable,
    Optional,
    Tuple,
    TypeVar,
)
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from ..abstractions.search import (
    AggregateSearchResult,
    GraphCommunityResult,
    GraphEntityResult,
    GraphRelationshipResult,
)
from ..abstractions.vector import VectorQuantizationType

if TYPE_CHECKING:
    from ..api.models.retrieval.responses import Citation

logger = logging.getLogger()


def reorder_collector_to_match_final_brackets(
    collector: Any,  # "SearchResultsCollector",
    final_citations: list["Citation"],
):
    """
    Rebuilds collector._results_in_order so that bracket i => aggregator[i-1].
    Each citation's rawIndex indicates which aggregator item the LLM used originally.
    We place that aggregator item in the new position for bracket 'index'.
    """
    old_list = collector.get_all_results()  # [(source_type, result_obj), ...]
    max_index = max((c.index for c in final_citations), default=0)
    new_list = [None] * max_index

    for cit in final_citations:
        old_idx = cit.rawIndex
        new_idx = cit.index
        if not old_idx:  # or old_idx <= 0
            continue
        pos = old_idx - 1
        if pos < 0 or pos >= len(old_list):
            continue
        # aggregator item is old_list[pos]
        # place it at new_list[new_idx - 1]
        if new_list[new_idx - 1] is None:
            new_list[new_idx - 1] = old_list[pos]

    # remove any None in case some indexes never got filled
    collector._results_in_order = [x for x in new_list if x is not None]


def map_citations_to_collector(
    citations: list["Citation"],
    collector: Any,  # "SearchResultsCollector"
) -> list["Citation"]:
    """
    For each citation, use its 'rawIndex' to look up the aggregator item from the
    collector. We then fill out the Citation’s sourceType, doc_id, text, metadata, etc.
    """
    from ..api.models.retrieval.responses import Citation

    # We'll build a dictionary aggregator_index -> (source_type, result_obj)
    aggregator_map = {}
    for stype, obj, agg_idx in collector.get_all_results():
        aggregator_map[agg_idx] = (stype, obj)

    mapped_citations: list[Citation] = []
    for cit in citations:
        old_ref = cit.rawIndex  # aggregator index we want
        if old_ref in aggregator_map:
            (source_type, result_obj) = aggregator_map[old_ref]
            # Make a copy with the updated fields
            updated = cit.copy()
            updated.sourceType = source_type

            # Fill chunk fields
            if source_type == "chunk":
                updated.id = str(result_obj.id)
                updated.document_id = str(result_obj.document_id)
                updated.owner_id = (
                    str(result_obj.owner_id) if result_obj.owner_id else None
                )
                updated.collection_ids = [
                    str(cid) for cid in result_obj.collection_ids
                ]
                updated.score = result_obj.score
                updated.text = result_obj.text
                updated.metadata = dict(result_obj.metadata)

            elif source_type == "graph":
                updated.score = result_obj.score
                updated.metadata = dict(result_obj.metadata)
                if result_obj.content:
                    updated.metadata["graphContent"] = (
                        result_obj.content.model_dump()
                    )

            elif source_type == "web":
                updated.metadata = {
                    "link": result_obj.link,
                    "title": result_obj.title,
                    "position": result_obj.position,
                    # etc. ...
                }

            elif source_type == "contextDoc":
                updated.metadata = {
                    "document": result_obj.document,
                    "chunks": result_obj.chunks,
                }

            else:
                # fallback unknown type
                updated.metadata = {}
            mapped_citations.append(updated)

        else:
            # aggregator index not found => out-of-range or unknown
            updated = cit.copy()
            updated.sourceType = None
            mapped_citations.append(updated)

    return mapped_citations


def _expand_citation_span_to_sentence(
    full_text: str, start: int, end: int
) -> Tuple[int, int]:
    """
    Return (sentence_start, sentence_end) for the sentence containing the bracket [n].
    We define a sentence boundary as '.', '?', or '!', optionally followed by
    spaces or a newline. This is a simple heuristic; you can refine it as needed.
    """
    sentence_enders = {".", "?", "!"}

    # Move backward from 'start' until we find a sentence ender or reach index 0
    s = start
    while s > 0:
        if full_text[s] in sentence_enders:
            s += 1
            while s < len(full_text) and full_text[s].isspace():
                s += 1
            break
        s -= 1
    sentence_start = s

    # Move forward from 'end' until we find a sentence ender or end of text
    e = end
    while e < len(full_text):
        if full_text[e] in sentence_enders:
            e += 1
            while e < len(full_text) and full_text[e].isspace():
                e += 1
            break
        e += 1
    sentence_end = e

    return (sentence_start, sentence_end)


def extract_citations(text: str) -> list["Citation"]:
    """
    Find bracket references like [3], [10], etc. Return a list of Citation objects
    whose 'index' field is the number found in brackets, but we will later rename
    that to 'rawIndex' to avoid confusion.
    """
    from ..api.models.retrieval.responses import Citation

    CITATION_PATTERN = re.compile(r"\[(\d+)\]")

    citations = []
    for match in CITATION_PATTERN.finditer(text):
        bracket_str = match.group(1)
        bracket_num = int(bracket_str)
        start_i = match.start()
        end_i = match.end()

        # Expand around the bracket to get a snippet if desired:
        snippet_start, snippet_end = _expand_citation_span_to_sentence(
            text, start_i, end_i
        )

        c = Citation(
            index=bracket_num,  # We'll rename this to rawIndex in step 2
            startIndex=start_i,
            endIndex=end_i,
            snippetStartIndex=snippet_start,
            snippetEndIndex=snippet_end,
        )
        citations.append(c)

    return citations


def reassign_citations_in_order(
    text: str, citations: list["Citation"]
) -> Tuple[str, list["Citation"]]:
    """
    Sort citations by their start index, unify repeated bracket numbers, and relabel them
    in ascending order of first appearance. Return (new_text, new_citations).
    - new_citations[i].index = the new bracket number
    - new_citations[i].rawIndex = the original bracket number
    """
    from ..api.models.retrieval.responses import Citation

    if not citations:
        return text, []

    # 1) Sort citations in order of their appearance
    sorted_cits = sorted(citations, key=lambda c: c.startIndex)

    # 2) Build a map from oldRef -> newRef
    old_to_new = {}
    next_new_index = 1
    labeled = []
    for cit in sorted_cits:
        old_ref = cit.index  # the bracket number we extracted
        if old_ref not in old_to_new:
            old_to_new[old_ref] = next_new_index
            next_new_index += 1
        new_ref = old_to_new[old_ref]

        # We create a "relabeled" citation that has `rawIndex=old_ref`
        # and `index=new_ref`.
        labeled.append(
            {
                "rawIndex": old_ref,
                "newIndex": new_ref,
                "startIndex": cit.startIndex,
                "endIndex": cit.endIndex,
            }
        )

    # 3) Replace the bracket references in the text from right-to-left
    #    so we don't mess up subsequent indices.
    result_chars = list(text)
    for item in sorted(labeled, key=lambda x: x["startIndex"], reverse=True):
        s_i = item["startIndex"]
        e_i = item["endIndex"]
        new_ref = item["newIndex"]
        replacement = f"[{new_ref}]"
        result_chars[s_i:e_i] = list(replacement)

    new_text = "".join(result_chars)

    # 4) Re-extract to get updated start/end indices, snippet offsets, etc.
    #    Then we merge that data with (rawIndex, newIndex).
    updated_citations = []
    updated_extracted = extract_citations(new_text)

    # We'll match them up in sorted order. Because they appear in the same order with the same count
    updated_extracted.sort(key=lambda c: c.startIndex)
    labeled.sort(key=lambda x: x["startIndex"])

    for labeled_item, updated_cit in zip(labeled, updated_extracted):
        c = Citation(
            rawIndex=labeled_item["rawIndex"],
            index=labeled_item["newIndex"],
            startIndex=updated_cit.startIndex,
            endIndex=updated_cit.endIndex,
            snippetStartIndex=updated_cit.snippetStartIndex,
            snippetEndIndex=updated_cit.snippetEndIndex,
        )
        updated_citations.append(c)

    return new_text, updated_citations


def format_search_results_for_llm(
    results: AggregateSearchResult,
    collector: Any,  # SearchResultsCollector
) -> str:
    """
    Instead of resetting 'source_counter' to 1, we:
     - For each chunk / graph / web / contextDoc in `results`,
     - Find the aggregator index from the collector,
     - Print 'Source [X]:' with that aggregator index.
    """
    lines = []

    # We'll build a quick helper to locate aggregator indices for each object:
    # Or you can rely on the fact that we've added them to the collector
    # in the same order. But let's do a "lookup aggregator index" approach:

    def get_aggregator_index_for_item(item):
        for stype, obj, agg_index in collector.get_all_results():
            if obj is item:
                return agg_index
        return None  # not found, fallback

    # 1) Chunk search
    if results.chunk_search_results:
        lines.append("Vector Search Results:")
        for c in results.chunk_search_results:
            agg_idx = get_aggregator_index_for_item(c)
            if agg_idx is None:
                # fallback if not found for some reason
                agg_idx = "???"
            lines.append(f"Source [{agg_idx}]:")
            lines.append(c.text or "")  # or c.text[:200] to truncate

    # 2) Graph search
    if results.graph_search_results:
        lines.append("Graph Search Results:")
        for g in results.graph_search_results:
            agg_idx = get_aggregator_index_for_item(g)
            if agg_idx is None:
                agg_idx = "???"
            lines.append(f"Source [{agg_idx}]:")
            if isinstance(g.content, GraphCommunityResult):
                lines.append(f"Community Name: {g.content.name}")
                lines.append(f"ID: {g.content.id}")
                lines.append(f"Summary: {g.content.summary}")
                # etc. ...
            elif isinstance(g.content, GraphEntityResult):
                lines.append(f"Entity Name: {g.content.name}")
                lines.append(f"Description: {g.content.description}")
            elif isinstance(g.content, GraphRelationshipResult):
                lines.append(
                    f"Relationship: {g.content.subject}-{g.content.predicate}-{g.content.object}"
                )
            # Add metadata if needed

    # 3) Web search
    if results.web_search_results:
        lines.append("Web Search Results:")
        for w in results.web_search_results:
            agg_idx = get_aggregator_index_for_item(w)
            if agg_idx is None:
                agg_idx = "???"
            lines.append(f"Source [{agg_idx}]:")
            lines.append(f"Title: {w.title}")
            lines.append(f"Link: {w.link}")
            lines.append(f"Snippet: {w.snippet}")

    # 4) Local context docs
    if results.context_document_results:
        lines.append("Local Context Documents:")
        for doc_result in results.context_document_results:
            agg_idx = get_aggregator_index_for_item(doc_result)
            if agg_idx is None:
                agg_idx = "???"
            doc_data = doc_result.document
            doc_title = doc_data.get("title", "Untitled Document")
            doc_id = doc_data.get("id", "N/A")
            summary = doc_data.get("summary", "")

            lines.append(f"Source [{agg_idx}]:")
            lines.append(f"Document Title: {doc_title} (ID: {doc_id})")
            if summary:
                lines.append(f"Summary: {summary}")

            # Then each chunk inside:
            for i, ch_text in enumerate(doc_result.chunks, start=1):
                lines.append(f"Chunk {i}: {ch_text}")

    return "\n".join(lines)


def format_search_results_for_stream(results: AggregateSearchResult) -> str:
    CHUNK_SEARCH_STREAM_MARKER = "chunk_search"
    GRAPH_SEARCH_STREAM_MARKER = "graph_search"
    WEB_SEARCH_STREAM_MARKER = "web_search"
    CONTEXT_STREAM_MARKER = "content"

    context = ""

    if results.chunk_search_results:
        context += f"<{CHUNK_SEARCH_STREAM_MARKER}>"
        vector_results_list = [
            r.as_dict() for r in results.chunk_search_results
        ]
        context += json.dumps(vector_results_list, default=str)
        context += f"</{CHUNK_SEARCH_STREAM_MARKER}>"

    if results.graph_search_results:
        context += f"<{GRAPH_SEARCH_STREAM_MARKER}>"
        graph_search_results_results_list = [
            r.dict() for r in results.graph_search_results
        ]
        context += json.dumps(graph_search_results_results_list, default=str)
        context += f"</{GRAPH_SEARCH_STREAM_MARKER}>"

    if results.web_search_results:
        context += f"<{WEB_SEARCH_STREAM_MARKER}>"
        web_results_list = [r.to_dict() for r in results.web_search_results]
        context += json.dumps(web_results_list, default=str)
        context += f"</{WEB_SEARCH_STREAM_MARKER}>"

    # NEW: local context
    if results.context_document_results:
        context += f"<{CONTEXT_STREAM_MARKER}>"
        # Just store them as raw dict JSON, or build a more structured form
        content_list = [
            cdr.to_dict() for cdr in results.context_document_results
        ]
        context += json.dumps(content_list, default=str)
        context += f"</{CONTEXT_STREAM_MARKER}>"

    return context


def _generate_id_from_label(label) -> UUID:
    return uuid5(NAMESPACE_DNS, label)


def generate_id(label: Optional[str] = None) -> UUID:
    """
    Generates a unique run id
    """
    return _generate_id_from_label(label if label != None else str(uuid4()))


def generate_document_id(filename: str, user_id: UUID) -> UUID:
    """
    Generates a unique document id from a given filename and user id
    """
    safe_filename = filename.replace("/", "_")
    return _generate_id_from_label(f"{safe_filename}-{str(user_id)}")


def generate_extraction_id(
    document_id: UUID, iteration: int = 0, version: str = "0"
) -> UUID:
    """
    Generates a unique extraction id from a given document id and iteration
    """
    return _generate_id_from_label(f"{str(document_id)}-{iteration}-{version}")


def generate_default_user_collection_id(user_id: UUID) -> UUID:
    """
    Generates a unique collection id from a given user id
    """
    return _generate_id_from_label(str(user_id))


def generate_user_id(email: str) -> UUID:
    """
    Generates a unique user id from a given email
    """
    return _generate_id_from_label(email)


def generate_default_prompt_id(prompt_name: str) -> UUID:
    """
    Generates a unique prompt id
    """
    return _generate_id_from_label(prompt_name)


def generate_entity_document_id() -> UUID:
    """
    Generates a unique document id inserting entities into a graph
    """
    generation_time = datetime.now().isoformat()
    return _generate_id_from_label(f"entity-{generation_time}")


def increment_version(version: str) -> str:
    prefix = version[:-1]
    suffix = int(version[-1])
    return f"{prefix}{suffix + 1}"


def decrement_version(version: str) -> str:
    prefix = version[:-1]
    suffix = int(version[-1])
    return f"{prefix}{max(0, suffix - 1)}"


def validate_uuid(uuid_str: str) -> UUID:
    return UUID(uuid_str)


def update_settings_from_dict(server_settings, settings_dict: dict):
    """
    Updates a settings object with values from a dictionary.
    """
    settings = deepcopy(server_settings)
    for key, value in settings_dict.items():
        if value is not None:
            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(getattr(settings, key), dict):
                        getattr(settings, key)[k] = v
                    else:
                        setattr(getattr(settings, key), k, v)
            else:
                setattr(settings, key, value)

    return settings


def _decorate_vector_type(
    input_str: str,
    quantization_type: VectorQuantizationType = VectorQuantizationType.FP32,
) -> str:
    return f"{quantization_type.db_type}{input_str}"


def _get_vector_column_str(
    dimension: int | float, quantization_type: VectorQuantizationType
) -> str:
    """
    Returns a string representation of a vector column type.

    Explicitly handles the case where the dimension is not a valid number
    meant to support embedding models that do not allow for specifying
    the dimension.
    """
    if math.isnan(dimension) or dimension <= 0:
        vector_dim = ""  # Allows for Postgres to handle any dimension
    else:
        vector_dim = f"({dimension})"
    return _decorate_vector_type(vector_dim, quantization_type)


KeyType = TypeVar("KeyType")


def deep_update(
    mapping: dict[KeyType, Any], *updating_mappings: dict[KeyType, Any]
) -> dict[KeyType, Any]:
    """
    Taken from Pydantic v1:
    https://github.com/pydantic/pydantic/blob/fd2991fe6a73819b48c906e3c3274e8e47d0f761/pydantic/utils.py#L200
    """
    updated_mapping = mapping.copy()
    for updating_mapping in updating_mappings:
        for k, v in updating_mapping.items():
            if (
                k in updated_mapping
                and isinstance(updated_mapping[k], dict)
                and isinstance(v, dict)
            ):
                updated_mapping[k] = deep_update(updated_mapping[k], v)
            else:
                updated_mapping[k] = v
    return updated_mapping
