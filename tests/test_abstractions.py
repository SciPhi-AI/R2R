import asyncio
import uuid

import pytest

from r2r import (
    AsyncPipe,
    AsyncState,
    Prompt,
    Vector,
    VectorEntry,
    VectorSearchRequest,
    VectorSearchResult,
    VectorType,
    generate_id_from_label,
)


@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


@pytest.fixture(scope="session", autouse=True)
async def cleanup_tasks():
    yield
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_async_state_update_and_get():
    state = AsyncState()
    outer_key = "test_key"
    values = {"inner_key": "value"}
    await state.update(outer_key, values)
    result = await state.get(outer_key, "inner_key")
    assert result == "value"


@pytest.mark.asyncio
async def test_async_state_delete():
    state = AsyncState()
    outer_key = "test_key"
    values = {"inner_key": "value"}
    await state.update(outer_key, values)
    await state.delete(outer_key, "inner_key")
    result = await state.get(outer_key, "inner_key")
    assert result == {}, "Expect empty result after deletion"


class MockAsyncPipe(AsyncPipe):
    async def _run_logic(self, input, state, run_id, *args, **kwargs):
        yield "processed"


@pytest.mark.asyncio
async def test_async_pipe_run():
    pipe = MockAsyncPipe()

    async def list_to_generator(lst):
        for item in lst:
            yield item

    input = pipe.Input(message=list_to_generator(["test"]))
    state = AsyncState()
    try:
        async_generator = await pipe.run(input, state)
        results = [result async for result in async_generator]
        assert results == ["processed"]
    except asyncio.CancelledError:
        pass  # Task cancelled as expected


def test_prompt_initialization_and_formatting():
    prompt = Prompt(
        name="greet", template="Hello, {name}!", input_types={"name": "str"}
    )
    formatted = prompt.format_prompt({"name": "Alice"})
    assert formatted == "Hello, Alice!"


def test_prompt_missing_input():
    prompt = Prompt(
        name="greet", template="Hello, {name}!", input_types={"name": "str"}
    )
    with pytest.raises(ValueError):
        prompt.format_prompt({})


def test_prompt_invalid_input_type():
    prompt = Prompt(
        name="greet", template="Hello, {name}!", input_types={"name": "int"}
    )
    with pytest.raises(TypeError):
        prompt.format_prompt({"name": "Alice"})


def test_search_request_with_optional_filters():
    request = VectorSearchRequest(
        query="test", limit=10, filters={"category": "books"}
    )
    assert request.query == "test"
    assert request.limit == 10
    assert request.filters == {"category": "books"}


def test_search_result_to_string():
    result = VectorSearchResult(
        id=generate_id_from_label("1"),
        score=9.5,
        metadata={"author": "John Doe"},
    )
    result_str = str(result)
    assert (
        result_str
        == f"VectorSearchResult(id={str(generate_id_from_label('1'))}, score=9.5, metadata={{'author': 'John Doe'}})"
    )


def test_search_result_repr():
    result = VectorSearchResult(
        id=generate_id_from_label("1"),
        score=9.5,
        metadata={"author": "John Doe"},
    )
    assert (
        repr(result)
        == f"VectorSearchResult(id={str(generate_id_from_label('1'))}, score=9.5, metadata={{'author': 'John Doe'}})"
    )


def test_vector_fixed_length_validation():
    with pytest.raises(ValueError):
        Vector(data=[1.0, 2.0], type=VectorType.FIXED, length=3)


def test_vector_entry_serialization():
    vector = Vector(data=[1.0, 2.0], type=VectorType.FIXED, length=2)
    entry_id = uuid.uuid4()
    entry = VectorEntry(
        id=entry_id, vector=vector, metadata={"key": uuid.uuid4()}
    )
    serializable = entry.to_serializable()
    assert serializable["id"] == str(entry_id)
    assert serializable["vector"] == [1.0, 2.0]
    assert isinstance(
        serializable["metadata"]["key"], str
    )  # Check UUID conversion to string
