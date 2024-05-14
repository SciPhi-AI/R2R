import uuid

import pytest

from r2r.core import (
    AsyncPipe,
    AsyncState,
    Prompt,
    SearchRequest,
    SearchResult,
    Vector,
    VectorEntry,
    VectorType,
)


# Testing AsyncState for state management
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


# Test AsyncPipe by creating a mock subclass
class MockAsyncPipe(AsyncPipe):
    async def _run_logic(self, input, state):
        yield "processed"


@pytest.mark.asyncio
async def test_async_pipe_run():
    pipe = MockAsyncPipe()
    async def list_to_generator(lst):
        for item in lst:
            yield item
    input = pipe.Input(message=list_to_generator(["test"]))
    state = AsyncState()
    async_generator = await pipe.run(input, state)
    results = [result async for result in async_generator]
    assert results == ["processed"]


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
    request = SearchRequest(
        query="test", limit=10, filters={"category": "books"}
    )
    assert request.query == "test"
    assert request.limit == 10
    assert request.filters == {"category": "books"}


def test_search_result_to_string():
    result = SearchResult(id="1", score=9.5, metadata={"author": "John Doe"})
    result_str = str(result)
    assert (
        result_str
        == "SearchResult(id=1, score=9.5, metadata={'author': 'John Doe'})"
    )


def test_search_result_repr():
    result = SearchResult(id="1", score=9.5, metadata={"author": "John Doe"})
    assert (
        repr(result)
        == "SearchResult(id=1, score=9.5, metadata={'author': 'John Doe'})"
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
