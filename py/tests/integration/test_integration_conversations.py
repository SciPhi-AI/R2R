import time
import contextlib
import uuid

import pytest

from r2r import R2RClient, R2RException


@pytest.fixture
def test_conversation(client: R2RClient):
    """Create and yield a test conversation, then clean up."""
    conv_resp = client.conversations.create()
    conversation_id = conv_resp.results.id
    yield conversation_id
    with contextlib.suppress(R2RException):
        client.conversations.delete(id=conversation_id)


def test_create_conversation(client: R2RClient):
    conv_id = client.conversations.create().results.id
    assert conv_id is not None, "No conversation_id returned"
    # Cleanup
    client.conversations.delete(id=conv_id)


def test_list_conversations(client: R2RClient, test_conversation):
    results = client.conversations.list(offset=0, limit=10).results
    # Just ensure at least one conversation is listed
    assert len(results) >= 1, "Expected at least one conversation, none found"


def test_retrieve_conversation(client: R2RClient, test_conversation):
    # Retrieve the conversation just created
    retrieved = client.conversations.retrieve(id=test_conversation).results
    # A new conversation might have no messages, so results should be an empty list
    assert isinstance(retrieved, list), "Expected list of messages"
    assert len(retrieved) == 0, (
        "Expected empty message list for a new conversation")


def test_delete_conversation(client: R2RClient):
    # Create a conversation and delete it
    conv_id = client.conversations.create().results.id
    client.conversations.delete(id=conv_id)

    # Verify retrieval fails
    with pytest.raises(R2RException) as exc_info:
        client.conversations.retrieve(id=conv_id)
    assert exc_info.value.status_code == 404, (
        "Wrong error code retrieving deleted conversation")


def test_add_message(client: R2RClient, test_conversation):
    # Add a message to the conversation
    msg_id = client.conversations.add_message(
        id=test_conversation,
        content="Hello",
        role="user",
    ).results.id
    assert msg_id, "No message ID returned after adding a message"

    # Retrieve conversation and verify message is present
    retrieved = client.conversations.retrieve(id=test_conversation).results
    found = any(str(msg.id) == str(msg_id) for msg in retrieved)
    assert found, "Added message not found in conversation"


def test_retrieve_non_existent_conversation(client: R2RClient):
    bad_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.conversations.retrieve(id=bad_id)
    assert exc_info.value.status_code == 404, (
        "Wrong error code for non-existent conversation")


def test_delete_non_existent_conversation(client: R2RClient):
    bad_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.conversations.delete(id=bad_id)
    assert exc_info.value.status_code == 404, (
        "Wrong error code for delete non-existent")


def test_add_message_to_non_existent_conversation(client: R2RClient):
    bad_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.conversations.add_message(
            id=bad_id,
            content="Hi",
            role="user",
        )
    # Expected a 404 since conversation doesn't exist
    assert exc_info.value.status_code == 404, (
        "Wrong error code for adding message to non-existent conversation")


def test_update_message(client: R2RClient, test_conversation):
    # Add a message first
    original_msg_id = client.conversations.add_message(
        id=test_conversation,
        content="Original content",
        role="user",
    ).results.id

    # Update the message
    update_resp = client.conversations.update_message(
        id=test_conversation,
        message_id=original_msg_id,
        content="Updated content",
        metadata={
            "new_key": "new_value"
        },
    ).results

    assert update_resp.message is not None, "No message returned after update"
    assert update_resp.metadata is not None, (
        "No metadata returned after update")
    assert update_resp.id is not None, "No metadata returned after update"

    # Retrieve the conversation with the new branch
    updated_conv = client.conversations.retrieve(id=test_conversation).results
    assert updated_conv, "No conversation returned after update"
    assert updated_conv[0].message.content == "Updated content", (
        "Message content not updated")
    # found_updated = any(msg["id"] == new_message_id and msg["message"]["content"] == "Updated content" for msg in updated_conv)
    # assert found_updated, "Updated message not found in the new branch"


def test_update_non_existent_message(client: R2RClient, test_conversation):
    fake_msg_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.conversations.update_message(id=test_conversation,
                                            message_id=fake_msg_id,
                                            content="Should fail")
    assert exc_info.value.status_code == 404, (
        "Wrong error code for updating non-existent message")


def test_add_message_with_empty_content(client: R2RClient, test_conversation):
    with pytest.raises(R2RException) as exc_info:
        client.conversations.add_message(
            id=test_conversation,
            content="",
            role="user",
        )
    # Check for 400 or a relevant error code depending on server validation
    assert exc_info.value.status_code == 400, (
        "Wrong error code or no error for empty content message")


def test_add_message_invalid_role(client: R2RClient, test_conversation):
    with pytest.raises(R2RException) as exc_info:
        client.conversations.add_message(
            id=test_conversation,
            content="Hello",
            role="invalid_role",
        )
    assert exc_info.value.status_code == 400, (
        "Wrong error code or no error for invalid role")


def test_add_message_to_deleted_conversation(client: R2RClient):
    # Create a conversation and delete it
    conv_id = client.conversations.create().results.id
    client.conversations.delete(id=conv_id)

    # Try adding a message to the deleted conversation
    with pytest.raises(R2RException) as exc_info:
        client.conversations.add_message(
            id=conv_id,
            content="Should fail",
            role="user",
        )
    assert exc_info.value.status_code == 404, (
        "Wrong error code for adding message to deleted conversation")


def test_update_message_with_additional_metadata(client: R2RClient,
                                                 test_conversation):
    # Add a message with initial metadata
    original_msg_id = client.conversations.add_message(
        id=test_conversation,
        content="Initial content",
        role="user",
        metadata={
            "initial_key": "initial_value"
        },
    ).results.id

    # Update the message with new content and additional metadata
    update_resp = client.conversations.update_message(
        id=test_conversation,
        message_id=original_msg_id,
        content="Updated content",
        metadata={
            "new_key": "new_value"
        },
    ).results

    # Retrieve the conversation from the new branch
    updated_conv = client.conversations.retrieve(id=test_conversation).results

    # Find the updated message
    updated_message = next(
        (msg for msg in updated_conv if str(msg.id) == str(original_msg_id)),
        None,
    )
    assert updated_message is not None, (
        "Updated message not found in conversation")

    # Check that metadata includes old keys, new keys, and 'edited': True
    msg_metadata = updated_message.metadata
    assert msg_metadata.get("initial_key") == "initial_value", (
        "Old metadata not preserved")
    assert msg_metadata.get("new_key") == "new_value", "New metadata not added"
    assert msg_metadata.get("edited") is True, (
        "'edited' flag not set in metadata")
    assert updated_message.message.content == "Updated content", (
        "Message content not updated")


def test_new_conversation_gets_named_after_first_agent_interaction(client: R2RClient):
    """Test that a new conversation is automatically named after the first agent interaction."""
    # Create a new conversation
    conv_resp = client.conversations.create()
    conversation_id = conv_resp.results.id

    try:
        # Verify it has no name initially
        conv_overview = client.conversations.list(
            offset=0,
            limit=10,
            # conversation_ids=[conversation_id]
        )

        target_conv = next((c for c in conv_overview.results if str(c.id) == str(conversation_id)), None)
        assert target_conv is not None, "Test conversation not found"
        assert target_conv.name is None, "New conversation already had a name"

        # Add a message via the agent method which should trigger naming
        response = client.retrieval.agent(
            message={"role": "user", "content": "Hello, this is a test message"},
            conversation_id=conversation_id,
        )
        time.sleep(5) # sleep while name is fetched
        # Verify the conversation now has a name
        conv_overview = client.conversations.list(
            offset=0,
            limit=10,
            # conversation_ids=[conversation_id]
        )
        target_conv = next((c for c in conv_overview.results if str(c.id) == str(conversation_id)), None)
        assert target_conv is not None, "Test conversation not found"
        assert target_conv.name is not None and target_conv.name != "", "Conversation was not automatically named"

    finally:
        # Cleanup
        client.conversations.delete(id=conversation_id)


def test_existing_named_conversation_preserves_name_after_agent_interaction(client: R2RClient):
    """Test that an existing conversation with a name preserves that name after agent interaction."""
    # Create a new conversation
    conv_resp = client.conversations.create()
    conversation_id = conv_resp.results.id

    try:
        # Set a specific name for the conversation
        custom_name = f"Custom Conversation Name {uuid.uuid4()}"
        client.conversations.update(
            id=conversation_id,
            name=custom_name
        )

        # Verify the name was set correctly
        conv_overview = client.conversations.list(
            offset=0,
            limit=10,
            # conversation_ids=[conversation_id]
        )
        target_conv = next((c for c in conv_overview.results if str(c.id) == str(conversation_id)), None)
        assert target_conv is not None, "Test conversation not found"
        assert target_conv.name == custom_name, "Custom name not set correctly"

        # Add a message via the agent method
        response = client.retrieval.agent(
            message={"role": "user", "content": "Hello, this is a test message"},
            conversation_id=conversation_id,
        )

        # Verify the conversation still has the same name
        conv_overview = client.conversations.list(
            offset=0,
            limit=100,
            # conversation_ids=[conversation_id]
        )

        target_conv = next((c for c in conv_overview.results if str(c.id) == str(conversation_id)), None)
        assert target_conv is not None, "Test conversation not found"
        assert target_conv.name == custom_name, "Conversation name was changed after agent interaction"

    finally:
        # Cleanup
        client.conversations.delete(id=conversation_id)
