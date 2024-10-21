import pytest

from core import Message


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
async def test_branches_overview(local_logging_provider):
    conversation_id = await local_logging_provider.create_conversation()
    message_id = await local_logging_provider.add_message(
        conversation_id, Message(role="user", content="Hello")
    )
    await local_logging_provider.edit_message(message_id, "Hello, edited")

    branches = await local_logging_provider.branches_overview(conversation_id)
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
        conversation_id,
        Message(role="assistant", content="Hi there!"),
        message_id_1,
    )

    branch_id = await local_logging_provider.branch_at_message(message_id_1)
    assert isinstance(branch_id, str)
    assert len(branch_id) > 0

    retrieved_messages = await local_logging_provider.get_conversation(
        conversation_id, branch_id
    )
    assert len(retrieved_messages) == 1
    assert retrieved_messages[0].content == "Hello"


@pytest.mark.asyncio
async def test_edit_message_in_middle(local_logging_provider):
    # Create a conversation with multiple messages
    conversation_id = await local_logging_provider.create_conversation()

    # Add initial messages
    message_id_1 = await local_logging_provider.add_message(
        conversation_id, Message(role="user", content="Hello")
    )
    message_id_2 = await local_logging_provider.add_message(
        conversation_id,
        Message(role="assistant", content="Hi there!"),
        message_id_1,
    )
    message_id_3 = await local_logging_provider.add_message(
        conversation_id,
        Message(role="user", content="How are you?"),
        message_id_2,
    )
    message_id_4 = await local_logging_provider.add_message(
        conversation_id,
        Message(role="assistant", content="I'm doing well, thanks!"),
        message_id_3,
    )

    # Edit message 2
    new_message_id, new_branch_id = await local_logging_provider.edit_message(
        message_id_2, "Greetings!"
    )

    # Retrieve messages in the new branch
    retrieved_messages = await local_logging_provider.get_conversation(
        conversation_id, new_branch_id
    )

    print("retrieved_messages = ", retrieved_messages)
    # Verify that messages after the edited message are not present
    assert len(retrieved_messages) == 2
    assert retrieved_messages[0].content == "Hello"
    assert retrieved_messages[0].role == "user"
    assert retrieved_messages[1].content == "Greetings!"
    assert retrieved_messages[1].role == "assistant"


@pytest.mark.asyncio
async def test_multiple_branches_from_same_message(local_logging_provider):
    # Create a conversation with initial messages
    conversation_id = await local_logging_provider.create_conversation()
    message_id_1 = await local_logging_provider.add_message(
        conversation_id, Message(role="user", content="Tell me a joke.")
    )
    message_id_2 = await local_logging_provider.add_message(
        conversation_id,
        Message(
            role="assistant", content="Why did the chicken cross the road?"
        ),
        message_id_1,
    )

    # Create first branch
    new_message_id_1, new_branch_id_1 = (
        await local_logging_provider.edit_message(
            message_id_2, "Knock, knock!"
        )
    )

    # Create second branch
    new_message_id_2, new_branch_id_2 = (
        await local_logging_provider.edit_message(
            message_id_2,
            "What do you call a bear with no teeth? A gummy bear!",
        )
    )

    # Retrieve messages for the first new branch
    retrieved_messages_1 = await local_logging_provider.get_conversation(
        conversation_id, new_branch_id_1
    )

    # Retrieve messages for the second new branch
    retrieved_messages_2 = await local_logging_provider.get_conversation(
        conversation_id, new_branch_id_2
    )

    # Verify first branch messages
    assert len(retrieved_messages_1) == 2
    assert retrieved_messages_1[0].content == "Tell me a joke."
    assert retrieved_messages_1[1].content == "Knock, knock!"

    # Verify second branch messages
    assert len(retrieved_messages_2) == 2
    assert retrieved_messages_2[0].content == "Tell me a joke."
    assert (
        retrieved_messages_2[1].content
        == "What do you call a bear with no teeth? A gummy bear!"
    )


@pytest.mark.asyncio
async def test_navigate_between_branches(local_logging_provider):
    # Create a conversation and add a message
    conversation_id = await local_logging_provider.create_conversation()
    message_id = await local_logging_provider.add_message(
        conversation_id,
        Message(role="user", content="What's the weather like?"),
    )

    # Create multiple branches by editing the message
    _, branch_id_1 = await local_logging_provider.edit_message(
        message_id, "What's the weather in New York?"
    )
    _, branch_id_2 = await local_logging_provider.edit_message(
        message_id, "What's the weather in London?"
    )
    _, branch_id_3 = await local_logging_provider.edit_message(
        message_id, "What's the weather in Tokyo?"
    )

    # Test navigating between branches
    next_branch = await local_logging_provider.get_next_branch(branch_id_1)
    assert next_branch == branch_id_2

    next_branch = await local_logging_provider.get_next_branch(branch_id_2)
    assert next_branch == branch_id_3

    prev_branch = await local_logging_provider.get_prev_branch(branch_id_3)
    assert prev_branch == branch_id_2

    prev_branch = await local_logging_provider.get_prev_branch(branch_id_2)
    assert prev_branch == branch_id_1


# @pytest.mark.asyncio
# async def test_messages_at_branch_point(local_logging_provider):
#     # Create a conversation with initial messages
#     conversation_id = await local_logging_provider.create_conversation()
#     user_message_id = await local_logging_provider.add_message(
#         conversation_id, Message(role="user", content="What's the capital of France?")
#     )
#     assistant_message_id = await local_logging_provider.add_message(
#         conversation_id, Message(role="assistant", content="The capital of France is Paris."), user_message_id
#     )

#     # Create multiple branches by editing the assistant's message
#     _, branch_id_1 = await local_logging_provider.edit_message(
#         assistant_message_id, "It's Paris."
#     )
#     _, branch_id_2 = await local_logging_provider.edit_message(
#         assistant_message_id, "Paris is the capital city of France."
#     )

#     # List all branches
#     branches = await local_logging_provider.branches_overview(conversation_id)

#     # Collect messages at the branching point
#     messages_at_branch_point = []
#     for branch in branches:
#         print('branch = ', branch)
#         if branch["branch_point_id"] == assistant_message_id:
#             # Get the message content at the branching point
#             content = Message.parse_raw(branch["content"]).content
#             messages_at_branch_point.append(content)

#     # Verify that all alternative messages are available
#     assert len(messages_at_branch_point) == 2
#     assert "It's Paris." in messages_at_branch_point
#     assert "Paris is the capital city of France." in messages_at_branch_point


@pytest.mark.asyncio
async def test_delete_branch(local_logging_provider):
    # Create a conversation and branches
    conversation_id = await local_logging_provider.create_conversation()
    message_id = await local_logging_provider.add_message(
        conversation_id,
        Message(role="user", content="Explain quantum physics."),
    )
    _, branch_id = await local_logging_provider.edit_message(
        message_id, "Explain quantum physics in simple terms."
    )

    # Delete the branch (assuming a delete_branch method exists)
    await local_logging_provider.delete_conversation(conversation_id)

    # Try to retrieve the deleted branch
    retrieved_messages = await local_logging_provider.get_conversation(
        conversation_id, branch_id
    )

    # Verify that the branch no longer exists
    assert retrieved_messages == []
