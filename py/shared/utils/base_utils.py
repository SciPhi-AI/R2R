import json
import logging
import math
import uuid
from abc import ABCMeta
from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, Tuple, TypeVar
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

import tiktoken

from ..abstractions import (
    AggregateSearchResult,
    AsyncSyncMeta,
    GraphCommunityResult,
    GraphEntityResult,
    GraphRelationshipResult,
)
from ..abstractions.vector import VectorQuantizationType

if TYPE_CHECKING:
    pass


logger = logging.getLogger()


def id_to_shorthand(id: str | UUID):
    return str(id)[0:7]


def format_search_results_for_llm(
    results: AggregateSearchResult,
    collector: Any,  # SearchResultsCollector
) -> str:
    """
    Instead of resetting 'source_counter' to 1, we:
     - For each chunk / graph / web / doc in `results`,
     - Find the aggregator index from the collector,
     - Print 'Source [X]:' with that aggregator index.
    """
    lines = []

    # We'll build a quick helper to locate aggregator indices for each object:
    # Or you can rely on the fact that we've added them to the collector
    # in the same order. But let's do a "lookup aggregator index" approach:

    # 1) Chunk search
    if results.chunk_search_results:
        lines.append("Vector Search Results:")
        for c in results.chunk_search_results:
            lines.append(f"Source ID [{id_to_shorthand(c.id)}]:")
            lines.append(c.text or "")  # or c.text[:200] to truncate

    # 2) Graph search
    if results.graph_search_results:
        lines.append("Graph Search Results:")
        for g in results.graph_search_results:
            lines.append(f"Source ID [{id_to_shorthand(g.id)}]:")
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
            lines.append(f"Source ID [{id_to_shorthand(w.id)}]:")
            lines.append(f"Title: {w.title}")
            lines.append(f"Link: {w.link}")
            lines.append(f"Snippet: {w.snippet}")

    # 4) Local context docs
    if results.document_search_results:
        lines.append("Local Context Documents:")
        for doc_result in results.document_search_results:
            doc_title = doc_result.title or "Untitled Document"
            doc_id = doc_result.id
            summary = doc_result.summary

            lines.append(f"Full Document ID: {doc_id}")
            lines.append(f"Shortened Document ID: {id_to_shorthand(doc_id)}")
            lines.append(f"Document Title: {doc_title}")
            if summary:
                lines.append(f"Summary: {summary}")

            if doc_result.chunks:
                # Then each chunk inside:
                for chunk in doc_result.chunks:
                    lines.append(
                        f"\nChunk ID {id_to_shorthand(chunk['id'])}:\n{chunk['text']}"
                    )

    result = "\n".join(lines)
    return result


def _generate_id_from_label(label) -> UUID:
    return uuid5(NAMESPACE_DNS, label)


def generate_id(label: Optional[str] = None) -> UUID:
    """Generates a unique run id."""
    return _generate_id_from_label(
        label if label is not None else str(uuid4())
    )


def generate_document_id(filename: str, user_id: UUID) -> UUID:
    """Generates a unique document id from a given filename and user id."""
    safe_filename = filename.replace("/", "_")
    return _generate_id_from_label(f"{safe_filename}-{str(user_id)}")


def generate_extraction_id(
    document_id: UUID, iteration: int = 0, version: str = "0"
) -> UUID:
    """Generates a unique extraction id from a given document id and
    iteration."""
    return _generate_id_from_label(f"{str(document_id)}-{iteration}-{version}")


def generate_default_user_collection_id(user_id: UUID) -> UUID:
    """Generates a unique collection id from a given user id."""
    return _generate_id_from_label(str(user_id))


def generate_user_id(email: str) -> UUID:
    """Generates a unique user id from a given email."""
    return _generate_id_from_label(email)


def generate_default_prompt_id(prompt_name: str) -> UUID:
    """Generates a unique prompt id."""
    return _generate_id_from_label(prompt_name)


def generate_entity_document_id() -> UUID:
    """Generates a unique document id inserting entities into a graph."""
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
    """Updates a settings object with values from a dictionary."""
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
    """Returns a string representation of a vector column type.

    Explicitly handles the case where the dimension is not a valid number meant
    to support embedding models that do not allow for specifying the dimension.
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


def tokens_count_for_message(message, encoding):
    """Return the number of tokens used by a single message."""
    tokens_per_message = 3

    num_tokens = 0
    num_tokens += tokens_per_message
    if message.get("function_call"):
        num_tokens += len(encoding.encode(message["function_call"]["name"]))
        num_tokens += len(
            encoding.encode(message["function_call"]["arguments"])
        )
    elif message.get("tool_calls"):
        for tool_call in message["tool_calls"]:
            num_tokens += len(encoding.encode(tool_call["function"]["name"]))
            num_tokens += len(
                encoding.encode(tool_call["function"]["arguments"])
            )
    else:
        if "content" in message:
            num_tokens += len(encoding.encode(message["content"]))

    return num_tokens


def num_tokens_from_messages(messages, model="gpt-4o"):
    """Return the number of tokens used by a list of messages for both user and assistant."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warning("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = 0
    for message_ in messages:
        tokens += tokens_count_for_message(message_, encoding)

        tokens += 3  # every reply is primed with assistant
    return tokens


class SearchResultsCollector:
    """
    Collects search results in the form (source_type, result_obj).
    Handles both object-oriented and dictionary-based search results.
    """

    def __init__(self):
        # We'll store a list of (source_type, result_obj)
        self._results_in_order = []

    @property
    def results(self):
        """Get the results list"""
        return self._results_in_order

    @results.setter
    def results(self, value):
        """
        Set the results directly, with automatic type detection for 'unknown' items
        Handles the format: [('unknown', {...}), ('unknown', {...})]
        """
        self._results_in_order = []

        if isinstance(value, list):
            for item in value:
                if isinstance(item, tuple) and len(item) == 2:
                    source_type, result_obj = item

                    # Only auto-detect if the source type is "unknown"
                    if source_type == "unknown":
                        detected_type = self._detect_result_type(result_obj)
                        self._results_in_order.append(
                            (detected_type, result_obj)
                        )
                    else:
                        self._results_in_order.append(
                            (source_type, result_obj)
                        )
                else:
                    # If not a tuple, detect and add
                    detected_type = self._detect_result_type(item)
                    self._results_in_order.append((detected_type, item))
        else:
            raise ValueError("Results must be a list")

    def add_aggregate_result(self, agg):
        """
        Flatten the chunk_search_results, graph_search_results, web_search_results,
        and document_search_results into the collector.
        """
        if hasattr(agg, "chunk_search_results") and agg.chunk_search_results:
            for c in agg.chunk_search_results:
                self._results_in_order.append(("chunk", c))

        if hasattr(agg, "graph_search_results") and agg.graph_search_results:
            for g in agg.graph_search_results:
                self._results_in_order.append(("graph", g))

        if hasattr(agg, "web_search_results") and agg.web_search_results:
            for w in agg.web_search_results:
                self._results_in_order.append(("web", w))

        if (
            hasattr(agg, "document_search_results")
            and agg.document_search_results
        ):
            for cd in agg.document_search_results:
                self._results_in_order.append(("doc", cd))

    def add_result(self, result_obj, source_type=None):
        """
        Add a single result object to the collector.
        If source_type is not provided, automatically detect the type.
        """
        if source_type:
            self._results_in_order.append((source_type, result_obj))
            return source_type

        detected_type = self._detect_result_type(result_obj)
        self._results_in_order.append((detected_type, result_obj))
        return detected_type

    def _detect_result_type(self, obj):
        """
        Detect the type of a result object based on its properties.
        Works with both object attributes and dictionary keys.
        """
        # Handle dictionary types first (common for web search results)
        if isinstance(obj, dict):
            # Web search pattern
            if all(k in obj for k in ["title", "link"]) and any(
                k in obj for k in ["snippet", "description"]
            ):
                return "web"

            # Check for graph dictionary patterns
            if "content" in obj and isinstance(obj["content"], dict):
                content = obj["content"]
                if all(k in content for k in ["name", "description"]):
                    return "graph"  # Entity
                if all(
                    k in content for k in ["subject", "predicate", "object"]
                ):
                    return "graph"  # Relationship
                if all(k in content for k in ["name", "summary"]):
                    return "graph"  # Community

            # Chunk pattern
            if all(k in obj for k in ["text", "id"]) and any(
                k in obj for k in ["score", "metadata"]
            ):
                return "chunk"

            # Context document pattern
            if "document" in obj and "chunks" in obj:
                return "doc"

            # Check for explicit type indicator
            if "type" in obj:
                type_val = str(obj["type"]).lower()
                if any(t in type_val for t in ["web", "organic"]):
                    return "web"
                if "graph" in type_val:
                    return "graph"
                if "chunk" in type_val:
                    return "chunk"
                if "document" in type_val:
                    return "doc"

        # Handle object attributes for OOP-style results
        if hasattr(obj, "result_type"):
            result_type = str(obj.result_type).lower()
            if result_type in ["entity", "relationship", "community"]:
                return "graph"

        # Check class name hints
        class_name = obj.__class__.__name__
        if "Graph" in class_name:
            return "graph"
        if "Chunk" in class_name:
            return "chunk"
        if "Web" in class_name:
            return "web"
        if "Document" in class_name:
            return "doc"

        # Check for object attribute patterns
        if hasattr(obj, "content"):
            content = obj.content
            if hasattr(content, "name") and hasattr(content, "description"):
                return "graph"  # Entity
            if hasattr(content, "subject") and hasattr(content, "predicate"):
                return "graph"  # Relationship
            if hasattr(content, "name") and hasattr(content, "summary"):
                return "graph"  # Community

        if (
            hasattr(obj, "text")
            and hasattr(obj, "id")
            and (hasattr(obj, "score") or hasattr(obj, "metadata"))
        ):
            return "chunk"

        if (
            hasattr(obj, "title")
            and hasattr(obj, "link")
            and hasattr(obj, "snippet")
        ):
            return "web"

        if hasattr(obj, "document") and hasattr(obj, "chunks"):
            return "doc"

        # Default when type can't be determined
        return "unknown"

    def find_by_short_id(self, short_id):
        """Find a result by its short ID prefix"""
        if not short_id:
            return None

        for source_type, result_obj in self._results_in_order:
            # Check dictionary objects
            if isinstance(result_obj, dict) and "id" in result_obj:
                result_id = str(result_obj["id"])
                does_match = result_id.startswith(short_id)

                if does_match:
                    return result_obj

            # Special handling for doc with chunks
            elif source_type == "doc":
                if str(result_obj.id).startswith(short_id):
                    return result_obj
                chunks = getattr(result_obj, "chunks", [])
                if chunks:
                    for chunk in chunks:
                        chunk_id = getattr(chunk, "id", None)
                        if chunk_id and str(chunk_id).startswith(short_id):
                            return chunk

            # Handle object with id attribute
            else:
                obj_id = getattr(result_obj, "id", None)
                if obj_id and str(obj_id).startswith(short_id):
                    # Convert to dict if possible
                    if hasattr(result_obj, "as_dict"):
                        return result_obj.as_dict()
                    elif hasattr(result_obj, "model_dump"):
                        return result_obj.model_dump()
                    elif hasattr(result_obj, "dict"):
                        return result_obj.dict()
                    else:
                        return result_obj

        return None

    def get_results_by_type(self, type_name):
        """Get all results of a specific type"""
        return [
            result_obj
            for source_type, result_obj in self._results_in_order
            if source_type == type_name
        ]

    def __repr__(self):
        """String representation showing counts by type"""
        type_counts = {}
        for source_type, _ in self._results_in_order:
            type_counts[source_type] = type_counts.get(source_type, 0) + 1

        return f"SearchResultsCollector with {len(self._results_in_order)} results: {type_counts}"

    def get_all_results(self) -> list[Tuple[str, Any]]:
        """
        Return list of (source_type, result_obj, aggregator_index),
        in the order appended.
        """
        return self._results_in_order


def convert_nonserializable_objects(obj):
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    if hasattr(obj, "as_dict"):
        obj = obj.as_dict()
    if hasattr(obj, "to_dict"):
        obj = obj.to_dict()

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


def dump_obj(obj) -> list[dict[str, Any]]:
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    elif hasattr(obj, "dict"):
        obj = obj.dict()
    elif hasattr(obj, "as_dict"):
        obj = obj.as_dict()
    elif hasattr(obj, "to_dict"):
        obj = obj.to_dict()
    obj = convert_nonserializable_objects(obj)

    return obj


def dump_collector(collector: SearchResultsCollector) -> list[dict[str, Any]]:
    dumped = []
    for source_type, result_obj in collector.get_all_results():
        # Get the dictionary from the result object
        if hasattr(result_obj, "model_dump"):
            result_dict = result_obj.model_dump()
        elif hasattr(result_obj, "dict"):
            result_dict = result_obj.dict()
        elif hasattr(result_obj, "as_dict"):
            result_dict = result_obj.as_dict()
        elif hasattr(result_obj, "to_dict"):
            result_dict = result_obj.to_dict()
        else:
            result_dict = (
                result_obj  # Fallback if no conversion method is available
            )

        # Use the recursive conversion on the entire dictionary
        result_dict = convert_nonserializable_objects(result_dict)

        dumped.append(
            {
                "source_type": source_type,
                "result": result_dict,
            }
        )
    return dumped


def num_tokens(text, model="gpt-4o"):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    """Return the number of tokens used by a list of messages for both user and assistant."""
    return len(encoding.encode(text, disallowed_special=()))


class CombinedMeta(AsyncSyncMeta, ABCMeta):
    pass


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


class SSEFormatter:
    """
    Enhanced formatter for Server-Sent Events (SSE) with citation tracking.
    Extends the existing SSEFormatter with improved citation handling.
    """

    @staticmethod
    async def yield_citation_event(
        citation_data: dict,
    ):
        """
        Emits a citation event with optimized payload.

        Args:
            citation_id: The short ID of the citation (e.g., 'abc1234')
            span: (start, end) position tuple for this occurrence
            payload: Source object (included only for first occurrence)
            is_new: Whether this is the first time we've seen this citation
            citation_id_counter: Optional counter for citation occurrences

        Yields:
            Formatted SSE event lines
        """

        # Include the full payload only for new citations
        if not citation_data.get("is_new") or "payload" not in citation_data:
            citation_data["payload"] = None

        # Yield the event
        async for line in yield_sse_event("citation", citation_data):
            yield line

    @staticmethod
    async def yield_final_answer_event(
        final_data: dict,
    ):
        # Yield the event
        async for line in yield_sse_event("final_answer", final_data):
            yield line

    # Include other existing SSEFormatter methods for compatibility
    @staticmethod
    async def yield_message_event(text_segment, msg_id=None):
        msg_id = msg_id or f"msg_{uuid.uuid4().hex[:8]}"
        msg_payload = {
            "id": msg_id,
            "object": "agent.message.delta",
            "delta": {
                "content": [
                    {
                        "type": "text",
                        "payload": {
                            "value": text_segment,
                            "annotations": [],
                        },
                    }
                ]
            },
        }
        async for line in yield_sse_event("message", msg_payload):
            yield line

    @staticmethod
    async def yield_thinking_event(text_segment, thinking_id=None):
        thinking_id = thinking_id or f"think_{uuid.uuid4().hex[:8]}"
        thinking_data = {
            "id": thinking_id,
            "object": "agent.thinking.delta",
            "delta": {
                "content": [
                    {
                        "type": "text",
                        "payload": {
                            "value": text_segment,
                            "annotations": [],
                        },
                    }
                ]
            },
        }
        async for line in yield_sse_event("thinking", thinking_data):
            yield line

    @staticmethod
    def yield_done_event():
        return "event: done\ndata: [DONE]\n\n"

    @staticmethod
    async def yield_error_event(error_message, error_id=None):
        error_id = error_id or f"err_{uuid.uuid4().hex[:8]}"
        error_payload = {
            "id": error_id,
            "object": "agent.error",
            "error": {"message": error_message, "type": "agent_error"},
        }
        async for line in yield_sse_event("error", error_payload):
            yield line

    @staticmethod
    async def yield_tool_call_event(tool_call_data):
        from ..api.models.retrieval.responses import ToolCallEvent

        tc_event = ToolCallEvent(event="tool_call", data=tool_call_data)
        async for line in yield_sse_event(
            "tool_call", tc_event.dict()["data"]
        ):
            yield line

    # New helper for emitting search results:
    @staticmethod
    async def yield_search_results_event(aggregated_results):
        payload = {
            "id": "search_1",
            "object": "rag.search_results",
            "data": aggregated_results.as_dict(),
        }
        async for line in yield_sse_event("search_results", payload):
            yield line

    @staticmethod
    async def yield_tool_result_event(tool_result_data):
        from ..api.models.retrieval.responses import ToolResultEvent

        tr_event = ToolResultEvent(event="tool_result", data=tool_result_data)
        async for line in yield_sse_event(
            "tool_result", tr_event.dict()["data"]
        ):
            yield line
