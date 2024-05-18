import asyncio
import uuid
from typing import AsyncGenerator, Any, TYPE_CHECKING
if TYPE_CHECKING:
    from ..pipeline.base import Pipeline

def generate_run_id() -> uuid.UUID:
    return uuid.uuid4()


def generate_id_from_label(label: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, label)


async def list_to_generator(lst):
    if not isinstance(lst, list):
        lst = [lst]
    for item in lst:
        yield item


def run_pipeline(pipeline: "Pipeline", input: Any, *args, **kwargs):
    if not isinstance(input, AsyncGenerator):
        input = list_to_generator(input)
    async def _run_pipeline(input, *args, **kwargs):
        return await pipeline.run(input, *args, **kwargs)
    return asyncio.run(_run_pipeline(input, *args, **kwargs))
