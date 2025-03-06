import json
import logging
import math
import re
from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, Tuple, TypeVar
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
    Each citation's raw_index indicates which aggregator item the LLM used originally.
    We place that aggregator item in the new position for bracket 'index'.
    """
    old_list = collector.get_all_results()  # [(source_type, result_obj), ...]
    max_index = max((c.index for c in final_citations), default=0)
    new_list = [None] * max_index

    for cit in final_citations:
        old_idx = cit.raw_index
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
    For each citation, use its 'raw_index' to look up the aggregator item from the
    collector. We then fill out the Citation’s source_type, doc_id, text, metadata, etc.
    """
    from ..api.models.retrieval.responses import Citation

    # We'll build a dictionary aggregator_index -> (source_type, result_obj)
    aggregator_map = {}
    for stype, obj, agg_idx in collector.get_all_results():
        aggregator_map[agg_idx] = (stype, obj)

    logger.debug(
        f"Performing `map_citations_to_collector` with aggregator map: {aggregator_map}."
    )

    mapped_citations: list[Citation] = []
    for cit in citations:
        old_ref = cit.raw_index  # aggregator index we want
        if old_ref in aggregator_map:
            (source_type, result_obj) = aggregator_map[old_ref]
            logger.debug(
                f"Performing citation extraction, cit={cit}, source_type={source_type}, result_obj={result_obj}"
            )

            # Make a copy with the updated fields
            updated = cit.copy()
            updated.source_type = source_type

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
                # updated.text = result_obj.text
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
                    # "snippet": result_obj.snippet,
                }

            elif source_type == "contextDoc":
                document = updated.metadata.pop("document", {})
                updated.document_id = document.get("id")
                updated.owner_id = document.get("owner_id")
                updated.collection_ids = document.get("collection_ids")
                # updated.text = document.get("chunks", [])[updated.raw_index - 1]
                updated.metadata = document.get("metadata")

            else:
                # fallback unknown type
                updated.metadata = {}
            mapped_citations.append(updated)

        else:
            # aggregator index not found => out-of-range or unknown
            updated = cit.copy()
            updated.source_type = None
            mapped_citations.append(updated)

    return mapped_citations


def _expand_citation_span_to_sentence(
    full_text: str, start: int, end: int
) -> Tuple[int, int]:
    """
    Unchanged from your existing code. We will reuse it so each sub-reference
    in a multi bracket has the same snippet boundaries.
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
    Extended to parse single or multiple references within one bracket.
    E.g. "[18]" => one Citation with index=18,
         "[3, 5]" => two Citations, both share start/end/snippet, but have index=3 and index=5.
    """
    from ..api.models.retrieval.responses import Citation

    citations: list[Citation] = []
    bracket_id_counter = 0
    BRACKET_PATTERN = re.compile(r"\[([^\]]+)\]")

    for match in BRACKET_PATTERN.finditer(text):
        bracket_text = match.group(1)  # e.g. "18, 20"
        start_i = match.start()
        end_i = match.end()

        # Expand snippet
        snippet_start, snippet_end = _expand_citation_span_to_sentence(
            text, start_i, end_i
        )

        # For consistent grouping later, we can store a bracket_id
        bracket_id_counter += 1
        bracket_id = f"B{bracket_id_counter}"  # e.g. "B1"

        # Now parse out all integers inside the bracket:
        # "18,20" => [18, 20]
        # " 3 , 5  " => [3,5], etc.
        nums_found = re.findall(r"\d+", bracket_text)
        # If no digits found, skip
        if not nums_found:
            continue

        # For each integer in that bracket, create a separate Citation
        for num_str in nums_found:
            old_ref = int(num_str)
            c = Citation(
                index=old_ref,  # We'll rename it raw_index later in reassign.
                start_index=start_i,
                end_index=end_i,
                snippet_start_index=snippet_start,
                snippet_end_index=snippet_end,
                bracket_id=bracket_id,
            )
            # We'll attach an extra attribute to track which bracket group this came from
            # so we can replace them together in re-labelling. You could also store this
            # in a separate map, but let's do it inline:
            # setattr(c, "bracket_id", bracket_id)
            # Optionally store the order within that bracket.
            citations.append(c)

    return citations


def reassign_citations_in_order(
    text: str, citations: list["Citation"]
) -> Tuple[str, list["Citation"]]:
    """
    Extended so that if one bracket has multiple references, we produce a single
    bracket with multiple new references, e.g. "[18, 20]" => "[1, 2]".

    1) If no citations => return original text & empty list
    2) Group citations by bracket_id (or by (start_index, end_index)).
    3) Build the oldRef->newRef map in the order brackets appear.
    4) Replace from right to left in the text, each bracket with e.g. "[1, 2]".
    5) Return (new_text, updated_citations).
    """
    from ..api.models.retrieval.responses import Citation

    if not citations:
        return text, []

    # ---- 1) group by bracket_id ----
    # Each bracket_id corresponds to a single matched bracket (start_index..end_index).
    # If you didn't store bracket_id, you could do:
    #   bracket_key = (cit.start_index, cit.end_index)
    from collections import defaultdict

    bracket_map = defaultdict(list)
    for c in citations:
        # bracket_id = (c.start_index, c.end_index) if you prefer
        bracket_id = getattr(c, "bracket_id", f"{c.start_index}-{c.end_index}")
        bracket_map[bracket_id].append(c)

    # We'll want to do the bracket replacements from right to left by their
    # start_index, so we don't mess up indexes for earlier brackets.
    # But first let's figure out the order we discover new references.
    # We'll keep a global oldRef->newRef map, assigned in the order encountered
    old_to_new = {}
    next_new_ref = 1

    # We also need a list of bracket groups in the order they appear in the text (lowest start_index first).
    # We'll store (start_index, bracket_id).
    bracket_order = []
    for bid, cits in bracket_map.items():
        first_cit = min(cits, key=lambda c: c.start_index)
        bracket_order.append((first_cit.start_index, bid))
    bracket_order.sort(key=lambda x: x[0])  # ascending by start_index

    # This final data structure will hold bracket replacements for each bracket_id
    bracket_replacements = {}

    # ---- 2) unify references in each bracket group in the order they appear inside that bracket ----
    for _, bid in bracket_order:
        # bracket_cits = bracket_map[bid], all share the same bracket region
        # We want them in the order they appear in the bracket text. If you want
        # strictly the order they appear in the original text, you might store
        # an "extractedOrder" or something, but let's just keep ascending by index below:
        bracket_cits = bracket_map[bid]

        # Sort them by the order of extraction or their oldRef, depending on your preference.
        # We'll do the order in which they appear in the *original citations* list to keep it stable.
        # That means first occurrence in `citations` => first in bracket.
        # or you can do bracket_cits.sort(key=lambda c: c.index).
        # We'll do stable sorting by their position in the original citations list:
        bracket_cits_sorted = sorted(
            bracket_cits, key=lambda c: citations.index(c)
        )

        # For each oldRef we haven't seen, assign a newRef
        # Then build a list of newRefs for this bracket
        bracket_new_refs = []
        for cit in bracket_cits_sorted:
            old_ref = cit.index  # the 'oldRef' from extraction
            if old_ref not in old_to_new:
                old_to_new[old_ref] = next_new_ref
                next_new_ref += 1
            new_ref = old_to_new[old_ref]
            bracket_new_refs.append(new_ref)

        # We produce a single bracket text like: "[1, 2, 5]"
        bracket_str = "[" + ", ".join(str(r) for r in bracket_new_refs) + "]"

        # We'll store this so we can replace the text in one shot (later).
        # All cits in bracket_map[bid] share the same (start_index, end_index).
        # So let's pick any one of them to get the text range.
        any_cit = bracket_cits[0]
        bracket_replacements[bid] = {
            "start": any_cit.start_index,
            "end": any_cit.end_index,
            "replacement": bracket_str,
            "cits": bracket_cits_sorted,
            "newRefs": bracket_new_refs,
        }

    # ---- 3) Now do the actual text replacements from right to left ----
    # Sort bracket_replacements by start desc
    bracket_repls_desc = sorted(
        bracket_replacements.values(), key=lambda x: x["start"], reverse=True
    )

    text_chars = list(text)
    for br_info in bracket_repls_desc:
        s_i = br_info["start"]
        e_i = br_info["end"]
        replacement = br_info["replacement"]
        text_chars[s_i:e_i] = list(replacement)

    new_text = "".join(text_chars)

    # ---- 4) update each Citation object with the final newRef ----
    # Also fix up snippet boundaries if you want to be fancy. We can leave them as-is or re‐compute.
    # We'll just keep them as-is for now.
    updated_citations: list[Citation] = []

    for bid in bracket_map.keys():
        br_info = bracket_replacements[bid]
        bracket_cits_sorted = br_info["cits"]
        bracket_new_refs = br_info["newRefs"]
        # zip them 1:1
        for cit_obj, new_ref in zip(bracket_cits_sorted, bracket_new_refs):
            # `cit_obj.index` = final bracket number
            cit_obj.raw_index = cit_obj.index  # store original
            cit_obj.index = new_ref
            updated_citations.append(cit_obj)

    # If you want them sorted by final start_index in ascending order:
    updated_citations.sort(key=lambda c: c.start_index)

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

    result = "\n".join(lines)
    return result


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
