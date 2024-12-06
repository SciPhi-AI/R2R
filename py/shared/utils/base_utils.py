import asyncio
import json
import logging
from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING, Any, AsyncGenerator, Iterable, Optional
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from ..abstractions.search import (
    AggregateSearchResult,
    KGCommunityResult,
    KGEntityResult,
    KGGlobalResult,
    KGRelationshipResult,
)
from ..abstractions.vector import VectorQuantizationType

logger = logging.getLogger()


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
        formatted_results.append("KG Search Results:")
        for kg_result in results.graph_search_results:
            try:
                formatted_results.extend((f"Source [{source_counter}]:",))
            except AttributeError:
                raise ValueError(f"Invalid KG search result: {kg_result}")
                # formatted_results.extend(
                #     (
                #         f"Source [{source_counter}]:",
                #         f"Type: {kg_result.content.type}",
                #     )
                # )

            if isinstance(kg_result.content, KGCommunityResult):
                formatted_results.extend(
                    (
                        f"Name: {kg_result.content.name}",
                        f"Summary: {kg_result.content.summary}",
                        # f"Rating: {kg_result.content.rating}",
                        # f"Rating Explanation: {kg_result.content.rating_explanation}",
                        # "Findings:",
                    )
                )
                # formatted_results.append(
                #     f"- {finding}" for finding in kg_result.content.findings
                # )
            elif isinstance(
                kg_result.content,
                KGEntityResult,
            ):
                formatted_results.extend(
                    [
                        f"Name: {kg_result.content.name}",
                        f"Description: {kg_result.content.description}",
                    ]
                )
            elif isinstance(kg_result.content, KGRelationshipResult):
                formatted_results.append(
                    f"Relationship: {kg_result.content.subject} - {kg_result.content.predicate} - {kg_result.content.object}",
                    # f"Description: {kg_result.content.description}"
                )

            if kg_result.metadata:
                formatted_results.append("Metadata:")
                formatted_results.extend(
                    f"- {key}: {value}"
                    for key, value in kg_result.metadata.items()
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

    return "\n".join(formatted_results)


def format_search_results_for_stream(result: AggregateSearchResult) -> str:
    CHUNK_SEARCH_STREAM_MARKER = "chunk_search"
    GRAPH_SEARCH_STREAM_MARKER = "graph_search"
    WEB_SEARCH_STREAM_MARKER = "web_search"

    context = ""

    if result.chunk_search_results:
        context += f"<{CHUNK_SEARCH_STREAM_MARKER}>"
        vector_results_list = [
            result.as_dict() for result in result.chunk_search_results
        ]
        context += json.dumps(vector_results_list, default=str)
        context += f"</{CHUNK_SEARCH_STREAM_MARKER}>"

    if result.graph_search_results:
        context += f"<{GRAPH_SEARCH_STREAM_MARKER}>"
        kg_results_list = [
            result.dict() for result in result.graph_search_results
        ]
        context += json.dumps(kg_results_list, default=str)
        context += f"</{GRAPH_SEARCH_STREAM_MARKER}>"

    if result.web_search_results:
        context += f"<{WEB_SEARCH_STREAM_MARKER}>"
        web_results_list = [
            result.to_dict() for result in result.web_search_results
        ]
        context += json.dumps(web_results_list, default=str)
        context += f"</{WEB_SEARCH_STREAM_MARKER}>"

    return context


if TYPE_CHECKING:
    from ..pipeline.base_pipeline import AsyncPipeline


def _generate_id_from_label(label) -> UUID:
    return uuid5(NAMESPACE_DNS, label)


def generate_id(label: Optional[str] = None) -> UUID:
    """
    Generates a unique run id
    """
    return _generate_id_from_label(label if label != None else str(uuid4()))


# def generate_id(label: Optional[str]= None) -> UUID:
#     """
#     Generates a unique run id
#     """
#     return _generate_id_from_label(str(uuid4(label)))


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


def _get_str_estimation_output(x: tuple[Any, Any]) -> str:
    if isinstance(x[0], int) and isinstance(x[1], int):
        return " - ".join(map(str, x))
    else:
        return " - ".join(f"{round(a, 2)}" for a in x)
