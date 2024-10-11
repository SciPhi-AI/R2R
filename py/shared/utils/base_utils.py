import asyncio
import json
import logging
from datetime import datetime
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


def generate_collection_id_from_name(collection_name: str) -> UUID:
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
    return _generate_id_from_label(
        f"{query}-{completion_start_time.isoformat()}"
    )


def generate_default_prompt_id(prompt_name: str) -> UUID:
    """
    Generates a unique prompt id
    """
    return _generate_id_from_label(prompt_name)


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


def llm_cost_per_million_tokens(
    model: str, input_output_ratio: float = 2
) -> float:
    """
    Returns the cost per million tokens for a given model and input/output ratio.

    Input/Output ratio is the ratio of input tokens to output tokens.

    """

    # improving this to use provider in the future

    model = model.split("/")[-1]  # simplifying assumption
    cost_dict = {
        "gpt-4o-mini": (0.15, 0.6),
        "gpt-4o": (2.5, 10),
    }

    if model in cost_dict:
        return (
            cost_dict[model][0] * input_output_ratio * cost_dict[model][1]
        ) / (1 + input_output_ratio)
    else:
        # use gpt-4o as default
        logger.warning(f"Unknown model: {model}. Using gpt-4o as default.")
        return (
            cost_dict["gpt-4o"][0]
            * input_output_ratio
            * cost_dict["gpt-4o"][1]
        ) / (1 + input_output_ratio)
