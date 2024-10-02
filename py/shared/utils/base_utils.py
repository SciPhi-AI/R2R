import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator, Iterable
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from ..abstractions.graph import EntityType, RelationshipType
from ..abstractions.search import (
    AggregateSearchResult,
    KGCommunityResult,
    KGEntityResult,
    KGGlobalResult,
    KGRelationshipResult,
)

logger = logging.getLogger(__name__)


def format_search_results_for_llm(results: AggregateSearchResult) -> str:
    formatted_results = []
    source_counter = 1

    if results.vector_search_results:
        formatted_results.append("Vector Search Results:")
        for result in results.vector_search_results:
            formatted_results.extend(
                (f"Source [{source_counter}]:", f"{result.text}")
            )
            source_counter += 1

    if results.kg_search_results:
        formatted_results.append("KG Search Results:")
        for kg_result in results.kg_search_results:
            formatted_results.extend(
                (
                    f"Source [{source_counter}]:",
                    f"Name: {kg_result.content.name}",
                )
            )

            if isinstance(kg_result.content, KGCommunityResult):
                formatted_results.extend(
                    (
                        f"Summary: {kg_result.content.summary}",
                        f"Rating: {kg_result.content.rating}",
                        f"Rating Explanation: {kg_result.content.rating_explanation}",
                        "Findings:",
                    )
                )
                formatted_results.extend(
                    f"- {finding}" for finding in kg_result.content.findings
                )
            elif isinstance(
                kg_result.content,
                (KGEntityResult, KGRelationshipResult, KGGlobalResult),
            ):
                formatted_results.append(
                    f"Description: {kg_result.content.description}"
                )

            if kg_result.metadata:
                formatted_results.append("Metadata:")
                formatted_results.extend(
                    f"- {key}: {value}"
                    for key, value in kg_result.metadata.items()
                )

            source_counter += 1

    return "\n".join(formatted_results)


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


def generate_run_id() -> UUID:
    return uuid5(NAMESPACE_DNS, str(uuid4()))


def generate_id_from_label(label: str) -> UUID:
    return uuid5(NAMESPACE_DNS, label)


def generate_default_user_collection_id(user_id: UUID) -> UUID:
    """Generate the default collection ID for a user."""
    return generate_id_from_label(f"{user_id}")


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
