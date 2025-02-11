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
    ChunkSearchResult,
    ContextDocumentResult,
    GraphCommunityResult,
    GraphEntityResult,
    GraphRelationshipResult,
    GraphSearchResult,
    WebSearchResult,
)
from ..abstractions.vector import VectorQuantizationType

if TYPE_CHECKING:
    from ..api.models.retrieval.responses import Citation

logger = logging.getLogger()


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


def my_extract_citations(text: str) -> list["Citation"]:
    """
    Parse the LLM-generated text and extract bracket references [n].
    For each bracket, also expand around the bracket to capture
    a sentence-based snippet if possible.
    """
    from ..api.models.retrieval.responses import Citation

    pattern = r"\[(\d+)\]"
    citations: list[Citation] = []

    for match in re.finditer(pattern, text):
        bracket_index = int(match.group(1))
        bracket_start = match.start()
        bracket_end = match.end()

        # Expand to sentence boundaries
        snippet_start, snippet_end = _expand_citation_span_to_sentence(
            text, bracket_start, bracket_end
        )
        snippet_text = text[snippet_start:snippet_end]

        # Build a typed Citation object
        citation = Citation(
            index=bracket_index,
            startIndex=bracket_start,
            endIndex=bracket_end,
            snippetStartIndex=snippet_start,
            snippetEndIndex=snippet_end,
            snippet=snippet_text,
        )
        citations.append(citation)

    return citations


def reassign_citations_in_order(
    text: str, citations: list["Citation"]
) -> Tuple[str, list["Citation"]]:
    """
    Sort citations by startIndex, assign them new indices [1..N], then
    replace the original bracket references in the text in-place. Re-extract
    citations from the modified text to capture new snippet data, and merge
    it back into typed Citation objects.
    """
    from ..api.models.retrieval.responses import Citation

    # Sort citations by startIndex
    sorted_citations = sorted(citations, key=lambda c: c.startIndex)

    # Convert text to char list for in-place editing
    result_text_chars = list(text)

    # Assign newIndex in ascending order
    labeled_citations = []
    for i, cit in enumerate(sorted_citations):
        new_idx = i + 1
        labeled_citations.append(
            {
                "oldIndex": cit.index,
                "newIndex": new_idx,
                "startIndex": cit.startIndex,
                "endIndex": cit.endIndex,
            }
        )

    # Replace references from end to start
    labeled_desc = sorted(
        labeled_citations, key=lambda x: x["startIndex"], reverse=True
    )
    for c_info in labeled_desc:
        start = c_info["startIndex"]
        end = c_info["endIndex"]
        new_idx = c_info["newIndex"]
        replacement = f"[{new_idx}]"
        result_text_chars[start:end] = list(replacement)

    # Build final text
    new_text = "".join(result_text_chars)

    # Re-extract to get updated bracket positions & snippet data
    re_extracted = my_extract_citations(new_text)
    re_map = {cit.index: cit for cit in re_extracted}

    # Merge snippet data & build final typed list in ascending order
    labeled_asc = sorted(labeled_citations, key=lambda x: x["newIndex"])
    updated_citations: list[Citation] = []
    for item in labeled_asc:
        new_idx = item["newIndex"]
        old_idx = item["oldIndex"]
        found = re_map.get(new_idx)

        if not found:
            # no match => fallback
            updated_citations.append(Citation(index=new_idx, oldIndex=old_idx))
            continue

        # copy snippet offsets & bracket offsets from found
        updated_citations.append(
            Citation(
                oldIndex=old_idx,
                index=new_idx,
                startIndex=found.startIndex,
                endIndex=found.endIndex,
                snippetStartIndex=found.snippetStartIndex,
                snippetEndIndex=found.snippetEndIndex,
                snippet=found.snippet,
            )
        )
    return new_text, updated_citations


def my_map_citations_to_sources(
    citations: list["Citation"], aggregated: AggregateSearchResult
) -> list["Citation"]:
    """
    Given typed citations (with snippet info) and an aggregated search result,
    map each bracket index to the corresponding source object (chunk, graph, web, context).
    Returns a new list of typed Citation objects, each storing source metadata.
    """
    flat_source_list = []

    # Flatten chunk -> graph -> web -> contextDoc in the same order your prompt enumerates them
    if aggregated.chunk_search_results:
        for chunk in aggregated.chunk_search_results:
            flat_source_list.append((chunk, "chunk"))
    if aggregated.graph_search_results:
        for g in aggregated.graph_search_results:
            flat_source_list.append((g, "graph"))
    if aggregated.web_search_results:
        for w in aggregated.web_search_results:
            flat_source_list.append((w, "web"))
    if aggregated.context_document_results:
        for cdoc in aggregated.context_document_results:
            flat_source_list.append((cdoc, "contextDoc"))

    mapped_citations: list[Citation] = []

    for cit in citations:
        idx = cit.index
        idx_0_based = idx - 1

        # If bracket index is out of range => placeholders
        if idx_0_based < 0 or idx_0_based >= len(flat_source_list):
            mapped_citations.append(cit)  # no updates to source fields
            continue

        source_obj, source_type = flat_source_list[idx_0_based]

        # Create a copy so we don't mutate the original
        updated_cit = cit.copy()
        updated_cit.sourceType = source_type

        # Fill out chunk-based metadata
        if source_type == "chunk":
            updated_cit.id = str(source_obj.id)
            updated_cit.document_id = str(source_obj.document_id)
            updated_cit.owner_id = (
                str(source_obj.owner_id) if source_obj.owner_id else None
            )
            updated_cit.collection_ids = [
                str(cid) for cid in source_obj.collection_ids
            ]
            updated_cit.score = source_obj.score
            updated_cit.text = source_obj.text
            updated_cit.metadata = dict(source_obj.metadata)

        elif source_type == "graph":
            updated_cit.score = source_obj.score
            updated_cit.metadata = dict(source_obj.metadata)
            if source_obj.content:
                updated_cit.metadata["graphContent"] = (
                    source_obj.content.model_dump()
                )

        elif source_type == "web":
            updated_cit.metadata = {
                "link": source_obj.link,
                "title": source_obj.title,
                "snippet": source_obj.snippet,
                "position": source_obj.position,
            }

        elif source_type == "contextDoc":
            updated_cit.metadata = {
                "document": source_obj.document,
                "chunks": source_obj.chunks,
            }

        mapped_citations.append(updated_cit)

    return mapped_citations


def format_search_results_for_llm(results: AggregateSearchResult) -> str:
    formatted_results = []
    source_counter = 1

    if results.chunk_search_results:
        formatted_results.append("Vector Search Results:")
        for result in results.chunk_search_results:
            formatted_results.extend(
                (f"Source [{source_counter}]:", f"{result.text}")
            )
            source_counter += 1

    if results.graph_search_results:
        formatted_results.append("Graph Search Results:")
        for graph_search_results_result in results.graph_search_results:
            try:
                formatted_results.extend((f"Source [{source_counter}]:",))
            except AttributeError:
                raise ValueError(
                    f"Invalid graph search result: {graph_search_results_result}"
                )

            if isinstance(
                graph_search_results_result.content, GraphCommunityResult
            ):
                formatted_results.extend(
                    (
                        f"Community Name: {graph_search_results_result.content.name}",
                        f"ID: {graph_search_results_result.content.id}",
                        f"Summary: {graph_search_results_result.content.summary}",
                        # f"Findings: {graph_search_results_result.content.findings}",
                    )
                )
            elif isinstance(
                graph_search_results_result.content,
                GraphEntityResult,
            ):
                formatted_results.extend(
                    [
                        f"Entity Name: {graph_search_results_result.content.name}",
                        f"ID: {graph_search_results_result.content.id}",
                        f"Description: {graph_search_results_result.content.description}",
                    ]
                )
            elif isinstance(
                graph_search_results_result.content, GraphRelationshipResult
            ):
                formatted_results.extend(
                    (
                        f"Relationship: {graph_search_results_result.content.subject} - {graph_search_results_result.content.predicate} - {graph_search_results_result.content.object}",
                        f"ID: {graph_search_results_result.content.id}",
                        f"Description: {graph_search_results_result.content.description}",
                        f"Subject ID: {graph_search_results_result.content.subject_id}",
                        f"Object ID: {graph_search_results_result.content.object_id}",
                    )
                )

            if graph_search_results_result.metadata:
                metadata_copy = graph_search_results_result.metadata.copy()
                metadata_copy.pop("associated_query", None)
                if metadata_copy:
                    formatted_results.append("Metadata:")
                    formatted_results.extend(
                        f"- {key}: {value}"
                        for key, value in metadata_copy.items()
                    )

            source_counter += 1
    if results.web_search_results:
        formatted_results.append("Web Search Results:")
        for result in results.web_search_results:
            formatted_results.extend(
                (
                    f"Source [{source_counter}]:",
                    f"Title: {result.title}",
                    f"Link: {result.link}",
                    f"Snippet: {result.snippet}",
                )
            )
            if result.date:
                formatted_results.append(f"Date: {result.date}")
            source_counter += 1

    # 4) NEW: If context_document_results is present:
    if results.context_document_results:
        formatted_results.append("Local Context Documents:")
        for doc_result in results.context_document_results:
            doc_data = doc_result.document
            chunks = doc_result.chunks
            doc_title = doc_data.get("title", "Untitled Document")
            doc_id = doc_data.get("id", "N/A")
            summary = doc_data.get("summary", "")

            formatted_results.append(
                f"Document Title: {doc_title} (ID: {doc_id})"
            )
            if summary:
                formatted_results.append(f"Summary: {summary}")

            # Then each chunk inside:
            formatted_results.extend(
                f"Chunk {i}: {ch}" for i, ch in enumerate(chunks, start=1)
            )

            source_counter += 1

    return "\n".join(formatted_results)


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
