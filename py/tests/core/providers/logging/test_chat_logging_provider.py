import pytest

from core import LocalRunLoggingProvider, LoggingConfig, Message


@pytest.mark.asyncio
async def test_create_conversation(local_logging_provider):
    conversation_id = await local_logging_provider.create_conversation()
    assert isinstance(conversation_id, str)
    assert len(conversation_id) > 0


@pytest.mark.asyncio
async def test_add_message(local_logging_provider):
    conversation_id = await local_logging_provider.create_conversation()
    message_id = await local_logging_provider.add_message(
        conversation_id, Message(role="user", content="Hello")
    )
    assert isinstance(message_id, str)
    assert len(message_id) > 0


@pytest.mark.asyncio
async def test_get_conversation(local_logging_provider):
    conversation_id = await local_logging_provider.create_conversation()
    messages = [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
    ]
    for message in messages:
        await local_logging_provider.add_message(conversation_id, message)

    retrieved_messages = await local_logging_provider.get_conversation(
        conversation_id
    )
    assert len(retrieved_messages) == len(messages)
    for original, retrieved in zip(messages, retrieved_messages):
        assert original.role == retrieved.role
        assert original.content == retrieved.content


@pytest.mark.asyncio
async def test_edit_message(local_logging_provider):
    conversation_id = await local_logging_provider.create_conversation()
    message_id = await local_logging_provider.add_message(
        conversation_id, Message(role="user", content="Hello")
    )
    new_message_id, new_branch_id = await local_logging_provider.edit_message(
        message_id, "Hello, edited"
    )
    assert isinstance(new_message_id, str)
    assert len(new_message_id) > 0
    assert isinstance(new_branch_id, str)
    assert len(new_branch_id) > 0

    retrieved_messages = await local_logging_provider.get_conversation(
        conversation_id, new_branch_id
    )
    assert len(retrieved_messages) == 1
    assert retrieved_messages[0].content == "Hello, edited"


@pytest.mark.asyncio
async def test_list_branches(local_logging_provider):
    conversation_id = await local_logging_provider.create_conversation()
    message_id = await local_logging_provider.add_message(
        conversation_id, Message(role="user", content="Hello")
    )
    await local_logging_provider.edit_message(message_id, "Hello, edited")

    branches = await local_logging_provider.list_branches(conversation_id)
    assert len(branches) == 2
    assert branches[0]["branch_point_id"] is None
    assert branches[1]["branch_point_id"] == message_id


@pytest.mark.asyncio
async def test_get_next_and_prev_branch(local_logging_provider):
    conversation_id = await local_logging_provider.create_conversation()
    message_id = await local_logging_provider.add_message(
        conversation_id, Message(role="user", content="Hello")
    )
    _, branch_id_1 = await local_logging_provider.edit_message(
        message_id, "Hello, edited 1"
    )
    _, branch_id_2 = await local_logging_provider.edit_message(
        message_id, "Hello, edited 2"
    )

    next_branch = await local_logging_provider.get_next_branch(branch_id_1)
    assert next_branch == branch_id_2

    prev_branch = await local_logging_provider.get_prev_branch(branch_id_2)
    assert prev_branch == branch_id_1


@pytest.mark.asyncio
async def test_branch_at_message(local_logging_provider):
    conversation_id = await local_logging_provider.create_conversation()
    message_id_1 = await local_logging_provider.add_message(
        conversation_id, Message(role="user", content="Hello")
    )
    message_id_2 = await local_logging_provider.add_message(
        conversation_id, Message(role="assistant", content="Hi there!")
    )

    branch_id = await local_logging_provider.branch_at_message(message_id_1)
    assert isinstance(branch_id, str)
    assert len(branch_id) > 0

    retrieved_messages = await local_logging_provider.get_conversation(
        conversation_id, branch_id
    )
    assert len(retrieved_messages) == 1
    assert retrieved_messages[0].content == "Hello"
