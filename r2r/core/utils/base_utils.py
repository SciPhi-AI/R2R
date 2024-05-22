import asyncio
import uuid
from typing import TYPE_CHECKING, Any, AsyncGenerator, Iterable

if TYPE_CHECKING:
    from ..pipeline.base_pipeline import Pipeline


def generate_run_id() -> uuid.UUID:
    return uuid.uuid4()


def generate_id_from_label(label: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, label)


async def to_async_generator(
    iterable: Iterable[Any],
) -> AsyncGenerator[Any, None]:
    for item in iterable:
        yield item


def run_pipeline(pipeline: "Pipeline", input: Any, *args, **kwargs):
    if not isinstance(input, AsyncGenerator) and not isinstance(input, list):
        print("a")
        input = to_async_generator([input])
    elif not isinstance(input, AsyncGenerator):
        print("b")
        input = to_async_generator(input)

    async def _run_pipeline(input, *args, **kwargs):
        return await pipeline.run(input, *args, **kwargs)

    return asyncio.run(_run_pipeline(input, *args, **kwargs))
