import asyncio
import json
from typing import TYPE_CHECKING, Any, AsyncGenerator, Generator, Iterable
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from ..abstractions.graph import EntityType, RelationshipType
from ..abstractions.search import AggregateSearchResult


def format_search_results_for_llm(
    results: AggregateSearchResult,
) -> str:
    formatted_results = ""
    if results.vector_search_results:
        formatted_results += "Vector Search Results:\n"
        for i, result in enumerate(results.vector_search_results):
            text = result.text
            formatted_results += f"{i+1}. {text}\n"

    if results.kg_search_results:
        if results.kg_search_results[0].local_result:
            formatted_results += "KG Local Search Results:\n"
            formatted_results += str(results.kg_search_results[0].local_result)
            formatted_results += "\n"

        if results.kg_search_results[0].global_result:
            formatted_results += "KG Global Search Results:\n"
            for i, result in enumerate(results.kg_search_results):
                formatted_results += f"{i+1}. {result}\n"

    return formatted_results


def format_search_results_for_stream(
    result: AggregateSearchResult,
) -> str:
    VECTOR_SEARCH_STREAM_MARKER = (
        "search"  # TODO - change this to vector_search in next major release
    )
    KG_LOCAL_SEARCH_STREAM_MARKER = "kg_local_search"
    KG_GLOBAL_SEARCH_STREAM_MARKER = "kg_global_search"

    context = ""
    if result.vector_search_results:
        context += f"<{VECTOR_SEARCH_STREAM_MARKER}>"
        vector_results_list = [
            result.json() for result in result.vector_search_results
        ]
        context += json.dumps(vector_results_list)
        context += f"</{VECTOR_SEARCH_STREAM_MARKER}>"

    if result.kg_search_results:
        if result.kg_search_results[0].local_result:
            context += f"<{KG_LOCAL_SEARCH_STREAM_MARKER}>"
            context += json.dumps(
                result.kg_search_results[0].local_result.json()
            )
            context += f"</{KG_LOCAL_SEARCH_STREAM_MARKER}>"

        if result.kg_search_results[0].global_result:
            context += f"<{KG_GLOBAL_SEARCH_STREAM_MARKER}>"
            for result in result.kg_search_results:
                context += json.dumps(result.global_result.json())
            context += f"</{KG_GLOBAL_SEARCH_STREAM_MARKER}>"
    return context


if TYPE_CHECKING:
    from ..pipeline.base_pipeline import AsyncPipeline


def generate_run_id() -> UUID:
    return uuid5(NAMESPACE_DNS, str(uuid4()))


def generate_id_from_label(label: str) -> UUID:
    return uuid5(NAMESPACE_DNS, label)


def generate_user_document_id(filename: str, user_id: UUID) -> UUID:
    """
    Generates a unique document id from a given filename and user id
    """
    return generate_id_from_label(f'{filename.split("/")[-1]}-{str(user_id)}')


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
