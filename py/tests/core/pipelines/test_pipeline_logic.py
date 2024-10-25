import asyncio
from typing import Any, AsyncGenerator

import pytest

from core import AsyncPipe, AsyncPipeline


class MultiplierPipe(AsyncPipe):
    def __init__(self, multiplier=1, delay=0, name="multiplier_pipe"):
        super().__init__(
            config=self.PipeConfig(name=name),
        )
        self.multiplier = multiplier
        self.delay = delay

    async def _run_logic(
        self,
        input: AsyncGenerator[Any, None],
        state,
        run_id=None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[Any, None]:
        async for item in input.message:
            if self.delay > 0:
                await asyncio.sleep(self.delay)  # Simulate processing delay
            if isinstance(item, list):
                processed = [x * self.multiplier for x in item]
            elif isinstance(item, int):
                processed = item * self.multiplier
            else:
                raise ValueError(f"Unsupported type: {type(item)}")
            yield processed


class FanOutPipe(AsyncPipe):
    def __init__(self, multiplier=1, delay=0, name="fan_out_pipe"):
        super().__init__(
            config=self.PipeConfig(name=name),
        )
        self.multiplier = multiplier
        self.delay = delay

    async def _run_logic(
        self,
        input: AsyncGenerator[Any, None],
        state,
        run_id=None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[Any, None]:
        inputs = []
        async for item in input.message:
            inputs.append(item)
        for it in range(self.multiplier):
            if self.delay > 0:
                await asyncio.sleep(self.delay)
            yield [(it + 1) * ele for ele in inputs]


class FanInPipe(AsyncPipe):
    def __init__(self, delay=0, name="fan_in_pipe"):
        super().__init__(
            config=self.PipeConfig(name=name),
        )
        self.delay = delay

    async def _run_logic(
        self,
        input: AsyncGenerator[Any, None],
        state,
        run_id=None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[Any, None]:
        total_sum = 0
        async for batch in input.message:
            if self.delay > 0:
                await asyncio.sleep(self.delay)  # Simulate processing delay
            total_sum += sum(
                batch
            )  # Assuming batch is iterable and contains numeric values
        yield total_sum


@pytest.fixture
def pipe_factory():
    def create_pipe(type, **kwargs):
        if type == "multiplier":
            return MultiplierPipe(**kwargs)
        elif type == "fan_out":
            return FanOutPipe(**kwargs)
        elif type == "fan_in":
            return FanInPipe(**kwargs)
        else:
            raise ValueError("Unsupported pipe type")

    return create_pipe


@pytest.mark.asyncio
@pytest.mark.parametrize("multiplier, delay, name", [(2, 0.1, "pipe")])
async def test_single_multiplier(pipe_factory, multiplier, delay, name):
    pipe = pipe_factory(
        "multiplier", multiplier=multiplier, delay=delay, name=name
    )

    async def input_generator():
        for i in [1, 2, 3]:
            yield i

    pipeline = AsyncPipeline()
    pipeline.add_pipe(pipe)

    result = []
    for output in await pipeline.run(input_generator()):
        result.append(output)

    expected_result = [i * multiplier for i in [1, 2, 3]]
    assert (
        result == expected_result
    ), "Pipeline output did not match expected multipliers"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "multiplier_a, delay_a, name_a, multiplier_b, delay_b, name_b",
    [(2, 0.1, "pipe_a", 2, 0.1, "pipe_b")],
)
async def test_double_multiplier(
    pipe_factory, multiplier_a, delay_a, name_a, multiplier_b, delay_b, name_b
):
    pipe_a = pipe_factory(
        "multiplier", multiplier=multiplier_a, delay=delay_a, name=name_a
    )
    pipe_b = pipe_factory(
        "multiplier", multiplier=multiplier_b, delay=delay_b, name=name_b
    )

    async def input_generator():
        for i in [1, 2, 3]:
            yield i

    pipeline = AsyncPipeline()
    pipeline.add_pipe(pipe_a)
    pipeline.add_pipe(pipe_b)

    result = []
    for output in await pipeline.run(input_generator()):
        result.append(output)

    expected_result = [i * multiplier_a * multiplier_b for i in [1, 2, 3]]
    assert (
        result == expected_result
    ), "Pipeline output did not match expected multipliers"


@pytest.mark.asyncio
@pytest.mark.parametrize("multiplier, delay, name", [(3, 0.1, "pipe")])
async def test_fan_out(pipe_factory, multiplier, delay, name):
    pipe = pipe_factory(
        "fan_out", multiplier=multiplier, delay=delay, name=name
    )

    async def input_generator():
        for i in [1, 2, 3]:
            yield i

    pipeline = AsyncPipeline()
    pipeline.add_pipe(pipe)

    result = []
    for output in await pipeline.run(input_generator()):
        result.append(output)

    expected_result = [
        [i + 1, 2 * (i + 1), 3 * (i + 1)] for i in range(multiplier)
    ]
    assert (
        result == expected_result
    ), "Pipeline output did not match expected multipliers"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "multiplier_a, delay_a, name_a, multiplier_b, delay_b, name_b",
    [
        (2, 0.1, "pipe_a", 2, 0.1, "pipe_b"),
        (4, 0.1, "pipe_a", 3, 0.1, "pipe_b"),
    ],
)
async def multiply_then_fan_out(
    pipe_factory, multiplier_a, delay_a, name_a, multiplier_b, delay_b, name_b
):
    pipe_a = pipe_factory(
        "multiplier", multiplier=multiplier_a, delay=delay_a, name=name_a
    )
    pipe_b = pipe_factory(
        "fan_out", multiplier=multiplier_b, delay=delay_b, name=name_b
    )

    async def input_generator():
        for i in [1, 2, 3]:
            yield i

    pipeline = AsyncPipeline()
    pipeline.add_pipe(pipe_a)
    pipeline.add_pipe(pipe_b)

    result = []
    async for output in await pipeline.run(input_generator()):
        result.append(output)

    expected_result = [[i * multiplier_a] async for i in input_generator()]
    assert (
        result[0] == expected_result
    ), "Pipeline output did not match expected multipliers"


@pytest.mark.asyncio
@pytest.mark.parametrize("multiplier, delay, name", [(3, 0.1, "pipe")])
async def test_fan_in_sum(pipe_factory, multiplier, delay, name):
    # Create fan-out to generate multiple streams
    fan_out_pipe = pipe_factory(
        "fan_out", multiplier=multiplier, delay=delay, name=f"{name}_a"
    )
    # Summing fan-in pipe
    fan_in_sum_pipe = pipe_factory("fan_in", delay=delay, name=f"{name}_b")

    async def input_generator():
        for i in [1, 2, 3]:
            yield i

    pipeline = AsyncPipeline()
    pipeline.add_pipe(fan_out_pipe)
    pipeline.add_pipe(fan_in_sum_pipe)

    result = await pipeline.run(input_generator())

    # Calculate expected results based on the multiplier and the sum of inputs
    expected_result = sum(
        sum(j * i for j in [1, 2, 3]) for i in range(1, multiplier + 1)
    )
    assert (
        result[0] == expected_result
    ), "Pipeline output did not match expected sums"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "multiplier_a, delay_a, name_a, multiplier_b, delay_b, name_b",
    [
        (3, 0.1, "pipe_a", 2, 0.1, "pipe_b"),
        (4, 0.1, "pipe_a", 3, 0.1, "pipe_b"),
    ],
)
async def test_fan_out_then_multiply(
    pipe_factory, multiplier_a, delay_a, name_a, multiplier_b, delay_b, name_b
):
    pipe_a = pipe_factory(
        "multiplier", multiplier=multiplier_a, delay=delay_a, name=name_a
    )
    pipe_b = pipe_factory(
        "fan_out", multiplier=multiplier_b, delay=delay_b, name=name_b
    )
    pipe_c = pipe_factory("fan_in", delay=0.1, name="pipe_c")

    async def input_generator():
        for i in [1, 2, 3]:
            yield i

    pipeline = AsyncPipeline()
    pipeline.add_pipe(pipe_a)
    pipeline.add_pipe(pipe_b)
    pipeline.add_pipe(pipe_c)

    result = await pipeline.run(input_generator())

    expected_result = sum(
        sum(j * i * multiplier_a for j in [1, 2, 3])
        for i in range(1, multiplier_b + 1)
    )
    assert (
        result[0] == expected_result
    ), "Pipeline output did not match expected multipliers"
