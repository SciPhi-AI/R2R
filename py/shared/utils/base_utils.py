import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator, Iterable
from datetime import datetime
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from ..abstractions.graph import EntityType, RelationshipType
from ..abstractions.search import AggregateSearchResult

logger = logging.getLogger(__name__)


def format_search_results_for_llm(
    results: AggregateSearchResult,
) -> str:
    formatted_results = ""
    i = 0
    if results.vector_search_results:
        formatted_results += "Vector Search Results:\n"
        for i, result in enumerate(results.vector_search_results):
            text = result.text
            formatted_results += f"Source [{i+1}]:\n{text}\n"

        i = len(results.vector_search_results)
    if results.kg_search_results:
        formatted_results += "KG Local Results:\n"
        for j, kg_result in enumerate(results.kg_search_results):
            formatted_results += (
                f"Source [{j+i+1}]: Name - {kg_result.content.name}\n"
            )
            formatted_results += (
                f"Description - {kg_result.content.description}\n"
            )
            findings = kg_result.metadata.get("findings", None)
            if findings:
                formatted_results += f"Supporting Findings: {findings}\n"

    return formatted_results


def format_search_results_for_stream(
    result: AggregateSearchResult,
) -> str:
    VECTOR_SEARCH_STREAM_MARKER = (
        "search"  # TODO - change this to vector_search in next major release
    )
    KG_SEARCH_STREAM_MARKER = "kg_search"

    context = ""
    if result.vector_search_results:
        context += f"<{VECTOR_SEARCH_STREAM_MARKER}>"
        vector_results_list = [
            result.as_dict() for result in result.vector_search_results
        ]
        context += json.dumps(vector_results_list, default=str)
        context += f"</{VECTOR_SEARCH_STREAM_MARKER}>"

    if result.kg_search_results:
        context += f"<{KG_SEARCH_STREAM_MARKER}>"
        kg_results_list = [
            result.dict() for result in result.kg_search_results
        ]
        context += json.dumps(kg_results_list, default=str)
        context += f"</{KG_SEARCH_STREAM_MARKER}>"

    return context


if TYPE_CHECKING:
    from ..pipeline.base_pipeline import AsyncPipeline


def _generate_id_from_label(label: str) -> UUID:
    return uuid5(NAMESPACE_DNS, label)

def generate_run_id() -> UUID:
    """
    Generates a unique run id
    """
    return _generate_id_from_label(str(uuid4()))

def generate_document_id(filename: str, user_id: UUID) -> UUID:
    """
    Generates a unique document id from a given filename and user id
    """
    return _generate_id_from_label(f'{filename.split("/")[-1]}-{str(user_id)}')

def generate_extraction_id(document_id: UUID, iteration: int, version: str) -> UUID:
    """
    Generates a unique extraction id from a given document id and iteration
    """
    return _generate_id_from_label(f"{str(document_id)}-{iteration}")

def generate_default_user_collection_id(user_id: UUID) -> UUID:
    """
    Generates a unique collection id from a given user id
    """
    return _generate_id_from_label(str(user_id))

def generate_collection_id(collection_name: str) -> UUID:
    """
    Generates a unique collection id from a given collection name
    """
    return _generate_id_from_label(collection_name)

def generate_user_id(email: str) -> UUID:
    """
    Generates a unique user id from a given email
    """
    return _generate_id_from_label(email)

def generate_message_id(query: str, completion_start_time: datetime) -> UUID:
    """
    Generates a unique message id from a given query and completion start time
    """
    return _generate_id_from_label(f"{query}-{completion_start_time.isoformat()}")


async def to_async_generator(
    iterable: Iterable[Any],
) -> AsyncGenerator[Any, None]:
    for item in iterable:
        yield item


def run_pipeline(pipeline: "AsyncPipeline", input: Any, *args, **kwargs):
    if not isinstance(input, AsyncGenerator):
        if not isinstance(input, list):
            input = to_async_generator([input])
        else:
            input = to_async_generator(input)

    async def _run_pipeline(input, *args, **kwargs):
        return await pipeline.run(input, *args, **kwargs)

    return asyncio.run(_run_pipeline(input, *args, **kwargs))


def increment_version(version: str) -> str:
    prefix = version[:-1]
    suffix = int(version[-1])
    return f"{prefix}{suffix + 1}"


def decrement_version(version: str) -> str:
    prefix = version[:-1]
    suffix = int(version[-1])
    return f"{prefix}{max(0, suffix - 1)}"


def format_entity_types(entity_types: list[EntityType]) -> str:
    lines = [entity.name for entity in entity_types]
    return "\n".join(lines)


def format_relations(predicates: list[RelationshipType]) -> str:
    lines = [predicate.name for predicate in predicates]
    return "\n".join(lines)

