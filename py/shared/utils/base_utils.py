import json
import logging
import math
import re
from copy import deepcopy
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Iterable, List, Optional, TypeVar
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

logger = logging.getLogger()


def my_extract_citations(text: str) -> List[Dict[str, int]]:
    """
    Finds references to the pattern [#] in the LLM-generated text and returns
    a list of dictionaries containing:
       - the citation index (as integer)
       - startIndex (character offset)
       - endIndex (character offset)

    Example:
      "Paris is the capital of France [1]."
      => { index: 1, startIndex: 31, endIndex: 34 }
    """
    pattern = r"\[(\d+)\]"
    citations = []
    for match in re.finditer(pattern, text):
        citations.append(
            {
                "index": int(match.group(1)),  # e.g. the '1' in "[1]"
                "startIndex": match.start(),  # character offset in text
                "endIndex": match.end(),
            }
        )
    return citations


def reassign_citations_in_order(
    text: str, citations: List[Dict[str, int]]
) -> (str, List[Dict[str, int]]):
    """
    Sorts the citations by their startIndex, then renumbers them [1], [2], [3], ...
    in the order they appear in the text. Also does an *in-place* replacement
    of the bracket references within 'text' so the final text has consecutively
    numbered citations.

    Returns:
      new_text: The text with bracket references replaced by the new indices
      new_citations: A list of citations with updated 'index', 'startIndex', 'endIndex'.

    Example:
      Original text: "DeepSeek-R1 is ... [9]. Also see [2]."
      Extracted citations:
        [ {index:9, startIndex:30, endIndex:33},
          {index:2, startIndex:45, endIndex:48} ]
      We reorder them by startIndex -> [9] first, [2] second
      We rename [9] -> [1], [2] -> [2].
    """

    # 1) Sort citations by the order they appear
    sorted_citations = sorted(citations, key=lambda c: c["startIndex"])

    # We will reconstruct text as a list of characters for easier in-place editing
    result_text_chars = list(text)
    offset = 0  # how many chars we've added/removed so far from modifications
    new_citations = []

    # 2) Because we're changing lengths, we replace from the *end* to the start
    #    so we don't disrupt the start/end indexes of upcoming replacements.
    #    But we still want the new indices assigned in ascending order, so we must do a 2-step approach:
    #      a) assign newIndex in ascending order
    #      b) do textual replacements in descending order
    #    We'll store these in a separate list for the actual replacement pass.
    labeled_citations = []
    for i, cit in enumerate(sorted_citations):
        new_idx = i + 1  # re-labeled index
        labeled_citations.append(
            {
                "oldIndex": cit["index"],
                "newIndex": new_idx,
                "startIndex": cit["startIndex"],
                "endIndex": cit["endIndex"],
            }
        )

    # Sort labeled citations in descending order of startIndex for safe replacement
    labeled_citations_desc = sorted(
        labeled_citations, key=lambda c: c["startIndex"], reverse=True
    )

    for citation_info in labeled_citations_desc:
        start = citation_info["startIndex"]
        end = citation_info["endIndex"]
        new_idx = citation_info["newIndex"]
        # old substring might be e.g. "[9]"
        old_length = end - start
        new_text_segment = f"[{new_idx}]"
        new_length = len(new_text_segment)
        # Replace in result_text_chars
        result_text_chars[start:end] = list(new_text_segment)
        # This effectively changes the length if new_length != old_length

    new_text = "".join(result_text_chars)

    # 3) Re-calculate final positions (startIndex/endIndex) for each citation
    #    We can just re-run the regex on new_text to get their final positions
    #    Or do a second pass of logic. Let's do the simpler approach: re-run the extraction
    re_extracted = my_extract_citations(new_text)

    # Now we have N re-extracted citations. They have the *same order* as the new labeled citations
    # because the new text has them in ascending order. We'll map them by newIndex -> that citation info
    reassign_map = {}
    for c in re_extracted:
        # c['index'] is the new index
        reassign_map[c["index"]] = c

    # 4) Build new_citations in ascending newIndex order
    labeled_citations_asc = sorted(
        labeled_citations, key=lambda c: c["newIndex"]
    )
    for citation_info in labeled_citations_asc:
        new_idx = citation_info["newIndex"]
        old_idx = citation_info["oldIndex"]
        # find the newly extracted position
        final_positions = reassign_map.get(new_idx, {})
        new_citations.append(
            {
                "oldIndex": old_idx,
                "index": new_idx,
                "startIndex": final_positions.get("startIndex"),
                "endIndex": final_positions.get("endIndex"),
            }
        )

    return new_text, new_citations


def my_map_citations_to_sources(
    citations: List[Dict[str, int]], aggregated: "AggregateSearchResult"
) -> List[Dict[str, Any]]:
    """
    Given the list of extracted citations (with indexes like 1,2,3...) and an
    AggregateSearchResult, return a list of 'citation objects' that
    include:
       - index, startIndex, endIndex (from citation detection)
       - sourceType: chunk, graph, web, or contextDoc
       - all relevant fields (id, document_id, owner_id, collection_ids, score, etc.)
       - any metadata, including text or titles

    We flatten out the search results in the order they were enumerated in the final prompt:
      1..N => chunk_search_results
      N+1..M => graph_search_results
      etc.
    """

    flat_source_list = []

    # 1) chunk_search_results
    if aggregated.chunk_search_results:
        for chunk in aggregated.chunk_search_results:
            flat_source_list.append((chunk, "chunk"))

    # 2) graph_search_results
    if aggregated.graph_search_results:
        for g in aggregated.graph_search_results:
            flat_source_list.append((g, "graph"))

    # 3) web_search_results
    if aggregated.web_search_results:
        for w in aggregated.web_search_results:
            flat_source_list.append((w, "web"))

    # 4) context_document_results
    if aggregated.context_document_results:
        for cdoc in aggregated.context_document_results:
            flat_source_list.append((cdoc, "contextDoc"))

    mapped_citations = []

    for c in citations:
        index_1_based = c["index"]
        idx_0_based = index_1_based - 1

        # If the LLM references a source index that doesn't exist, store placeholders
        if idx_0_based < 0 or idx_0_based >= len(flat_source_list):
            mapped_citations.append(
                {
                    "index": index_1_based,
                    "startIndex": c["startIndex"],
                    "endIndex": c["endIndex"],
                    "sourceType": None,
                    "id": None,
                    "document_id": None,
                    "owner_id": None,
                    "collection_ids": None,
                    "score": None,
                    "text": None,
                    "metadata": {},
                }
            )
            continue

        source_obj, source_type = flat_source_list[idx_0_based]

        citation_obj = {
            "index": index_1_based,
            "startIndex": c["startIndex"],
            "endIndex": c["endIndex"],
            "sourceType": source_type,
            "id": None,
            "document_id": None,
            "owner_id": None,
            "collection_ids": None,
            "score": None,
            "text": None,
            # We'll store all leftover fields in "metadata" to keep them structured
            "metadata": {},
        }

        # Now handle each source type and gather relevant fields:
        if source_type == "chunk":
            # source_obj is a ChunkSearchResult
            citation_obj.update(
                {
                    "id": str(source_obj.id),
                    "document_id": str(source_obj.document_id),
                    "owner_id": (
                        str(source_obj.owner_id)
                        if source_obj.owner_id
                        else None
                    ),
                    "collection_ids": [
                        str(cid) for cid in source_obj.collection_ids
                    ],
                    "score": source_obj.score,
                    "text": source_obj.text,
                    # For chunk metadata, let's unify them under "metadata"
                    "metadata": dict(source_obj.metadata),
                }
            )

        elif source_type == "graph":
            # source_obj is a GraphSearchResult
            # e.g. source_obj.content might be GraphEntityResult or GraphRelationshipResult
            citation_obj.update(
                {
                    "id": None,  # GraphSearchResult doesn't have an "id" at top-level
                    "document_id": None,
                    "owner_id": None,
                    "collection_ids": None,
                    "score": source_obj.score,
                    "text": None,  # Not typical to have a 'text' in a graph result
                    # entire "metadata" can go under citation_obj["metadata"]
                    "metadata": dict(source_obj.metadata),
                }
            )
            # You can add subfields from the content if you wish, e.g.:
            if source_obj.content:
                citation_obj["metadata"][
                    "graphContent"
                ] = source_obj.content.model_dump()

        elif source_type == "web":
            # source_obj is a WebSearchResult
            citation_obj.update(
                {
                    "id": None,
                    "document_id": None,
                    "owner_id": None,
                    "collection_ids": None,
                    "score": None,
                    "text": None,
                    "metadata": {
                        # Here we can store link, title, snippet, etc.
                        "link": source_obj.link,
                        "title": source_obj.title,
                        "snippet": source_obj.snippet,
                        "position": source_obj.position,
                    },
                }
            )

        elif source_type == "contextDoc":
            # source_obj is a ContextDocumentResult
            # That means source_obj.document is a dict with some fields:
            citation_obj.update(
                {
                    "id": None,
                    "document_id": None,
                    "owner_id": None,
                    "collection_ids": None,
                    "score": None,
                    "text": None,
                    # store the doc data (title, etc.) in metadata
                    "metadata": {
                        "document": source_obj.document,
                        "chunks": source_obj.chunks,
                    },
                }
            )

        mapped_citations.append(citation_obj)

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


async def to_async_generator(
    iterable: Iterable[Any],
) -> AsyncGenerator[Any, None]:
    for item in iterable:
        yield item


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
