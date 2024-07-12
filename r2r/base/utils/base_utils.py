import asyncio
import uuid
from typing import TYPE_CHECKING, Any, AsyncGenerator, Iterable

if TYPE_CHECKING:
    from ..pipeline.base_pipeline import AsyncPipeline


def generate_run_id() -> uuid.UUID:
    return uuid.uuid4()


def generate_id_from_label(label: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, label)


async def to_async_generator(
    iterable: Iterable[Any],
) -> AsyncGenerator[Any, None]:
    for item in iterable:
        yield item


def run_pipeline(pipeline: "AsyncPipeline", input: Any, *args, **kwargs):
    if not isinstance(input, AsyncGenerator) and not isinstance(input, list):
        input = to_async_generator([input])
    elif not isinstance(input, AsyncGenerator):
        input = to_async_generator(input)

    async def _run_pipeline(input, *args, **kwargs):
        return await pipeline.run(input, *args, **kwargs)

    return asyncio.run(_run_pipeline(input, *args, **kwargs))


def increment_version(version: str) -> str:
    prefix = version[:-1]
    suffix = int(version[-1])
    return f"{prefix}{suffix + 1}"


class EntityType:
    def __init__(self, name: str):
        self.name = name


class Relation:
    def __init__(self, name: str):
        self.name = name


def format_entity_types(entity_types: list[EntityType]) -> str:
    lines = []
    for entity in entity_types:
        lines.append(entity.name)
    return "\n".join(lines)


def format_relations(predicates: list[Relation]) -> str:
    lines = []
    for predicate in predicates:
        lines.append(predicate.name)
    return "\n".join(lines)
