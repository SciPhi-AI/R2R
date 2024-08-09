import asyncio
import uuid
from datetime import datetime

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
from r2r.base.abstractions.completion import CompletionRecord, MessageType
from r2r.base.abstractions.search import AggregateSearchResult


@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="function", autouse=True)
async def cleanup_tasks():
    yield
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)


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


def test_message_type_enum():
    assert str(MessageType.SYSTEM) == "system"
    assert str(MessageType.USER) == "user"
    assert str(MessageType.ASSISTANT) == "assistant"
    assert str(MessageType.FUNCTION) == "function"
    assert str(MessageType.TOOL) == "tool"


def test_completion_record_initialization():
    record = CompletionRecord(
        message_id=uuid.uuid4(),
        message_type=MessageType.USER,
        search_query="test query",
        llm_response="test response",
    )
    assert isinstance(record.message_id, uuid.UUID)
    assert record.message_type == MessageType.USER
    assert isinstance(record.timestamp, datetime)
    assert record.search_query == "test query"
    assert record.llm_response == "test response"


def test_completion_record_optional_fields():
    record = CompletionRecord(
        message_id=uuid.uuid4(), message_type=MessageType.SYSTEM
    )
    assert record.feedback is None
    assert record.score is None
    assert record.completion_start_time is None
    assert record.completion_end_time is None
    assert record.search_query is None
    assert record.search_results is None
    assert record.llm_response is None


def test_completion_record_to_dict():
    search_results = AggregateSearchResult(vector_search_results=[])
    record = CompletionRecord(
        message_id=uuid.uuid4(),
        message_type=MessageType.ASSISTANT,
        feedback=["Good"],
        score=[0.9],
        completion_start_time=datetime(2023, 1, 1, 12, 0),
        completion_end_time=datetime(2023, 1, 1, 12, 1),
        search_query="test",
        search_results=search_results,
        llm_response="Response",
    )
    record_dict = record.to_dict()

    assert isinstance(record_dict["message_id"], str)
    assert record_dict["message_type"] == "assistant"
    assert isinstance(record_dict["timestamp"], str)
    assert record_dict["feedback"] == ["Good"]
    assert record_dict["score"] == [0.9]
    assert record_dict["completion_start_time"] == "2023-01-01T12:00:00"
    assert record_dict["completion_end_time"] == "2023-01-01T12:01:00"
    assert record_dict["search_query"] == "test"
    assert isinstance(record_dict["search_results"], dict)
    assert record_dict["llm_response"] == "Response"


def test_completion_record_to_json():
    record = CompletionRecord(
        message_id=uuid.uuid4(),
        message_type=MessageType.FUNCTION,
        llm_response="JSON test",
    )
    json_str = record.to_json()
    assert isinstance(json_str, str)

    import json

    parsed_dict = json.loads(json_str)
    assert parsed_dict["message_type"] == "function"
    assert parsed_dict["llm_response"] == "JSON test"


@pytest.mark.parametrize("message_type", list(MessageType))
def test_completion_record_all_message_types(message_type):
    record = CompletionRecord(
        message_id=uuid.uuid4(), message_type=message_type
    )
    assert record.message_type == message_type


def test_completion_record_serialization_with_none_values():
    record = CompletionRecord(
        message_id=uuid.uuid4(), message_type=MessageType.TOOL
    )
    record_dict = record.to_dict()
    for field in [
        "feedback",
        "score",
        "completion_start_time",
        "completion_end_time",
        "search_query",
        "search_results",
        "llm_response",
    ]:
        assert record_dict[field] is None


def test_completion_record_with_complex_search_results():
    from r2r import VectorSearchResult

    search_result = VectorSearchResult(
        id=uuid.uuid4(), score=0.95, metadata={"key": "value"}
    )
    aggregate_result = AggregateSearchResult(
        vector_search_results=[search_result]
    )
    record = CompletionRecord(
        message_id=uuid.uuid4(),
        message_type=MessageType.USER,
        search_results=aggregate_result,
    )
    record_dict = record.to_dict()
    assert isinstance(record_dict["search_results"], dict)
    assert isinstance(
        record_dict["search_results"]["vector_search_results"], list
    )
    assert len(record_dict["search_results"]["vector_search_results"]) == 1
    assert (
        record_dict["search_results"]["vector_search_results"][0]["score"]
        == 0.95
    )
    assert record_dict["search_results"]["vector_search_results"][0][
        "metadata"
    ] == {"key": "value"}
