import uuid

import pytest

from fuse import FUSEClient, FUSEException


@pytest.fixture
def test_conversation(client):
    """Create and yield a test conversation, then clean up."""
    conv_resp = client.conversations.create()
    conversation_id = conv_resp["results"]["id"]
    yield conversation_id
    # Cleanup: Try deleting the conversation if it still exists
    try:
        client.conversations.delete(id=conversation_id)
    except FUSEException:
        pass


def test_create_conversation(client):
    resp = client.conversations.create()["results"]
    conv_id = resp["id"]
    assert conv_id is not None, "No conversation_id returned"
    # Cleanup
    client.conversations.delete(id=conv_id)


def test_list_conversations(client, test_conversation):
    listed = client.conversations.list(offset=0, limit=10)
    results = listed["results"]
    # Just ensure at least one conversation is listed
    assert len(results) >= 1, "Expected at least one conversation, none found"


def test_retrieve_conversation(client, test_conversation):
    # Retrieve the conversation just created
    retrieved = client.conversations.retrieve(id=test_conversation)["results"]
    # A new conversation might have no messages, so results should be an empty list
    assert isinstance(retrieved, list), "Expected list of messages"
    assert (
        len(retrieved) == 0
    ), "Expected empty message list for a new conversation"


def test_delete_conversation(client):
    # Create a conversation and delete it
    conv = client.conversations.create()["results"]
    conv_id = conv["id"]
    client.conversations.delete(id=conv_id)

    # Verify retrieval fails
    with pytest.raises(FUSEException) as exc_info:
        client.conversations.retrieve(id=conv_id)
    assert (
        exc_info.value.status_code == 404
    ), "Wrong error code retrieving deleted conversation"


def test_add_message(client, test_conversation):
    # Add a message to the conversation
    msg_resp = client.conversations.add_message(
        id=test_conversation,
        content="Hello",
        role="user",
    )["results"]
    msg_id = msg_resp["id"]
    assert msg_id, "No message ID returned after adding a message"

    # Retrieve conversation and verify message is present
    retrieved = client.conversations.retrieve(id=test_conversation)["results"]
    found = any(msg["id"] == msg_id for msg in retrieved)
    assert found, "Added message not found in conversation"


def test_retrieve_non_existent_conversation(client):
    bad_id = str(uuid.uuid4())
    with pytest.raises(FUSEException) as exc_info:
        client.conversations.retrieve(id=bad_id)
    assert (
        exc_info.value.status_code == 404
    ), "Wrong error code for non-existent conversation"


def test_delete_non_existent_conversation(client):
    bad_id = str(uuid.uuid4())
    with pytest.raises(FUSEException) as exc_info:
        result = client.conversations.delete(id=bad_id)
    assert (
        exc_info.value.status_code == 404
    ), "Wrong error code for delete non-existent"


def test_add_message_to_non_existent_conversation(client):
    bad_id = str(uuid.uuid4())
    with pytest.raises(FUSEException) as exc_info:
        client.conversations.add_message(
            id=bad_id,
            content="Hi",
            role="user",
        )
    # Expected a 404 since conversation doesn't exist
    assert (
        exc_info.value.status_code == 404
    ), "Wrong error code for adding message to non-existent conversation"


def test_update_message(client, test_conversation):
    # Add a message first
    msg_resp = client.conversations.add_message(
        id=test_conversation,
        content="Original content",
        role="user",
    )["results"]
    original_msg_id = msg_resp["id"]

    # Update the message
    update_resp = client.conversations.update_message(
        id=test_conversation,
        message_id=original_msg_id,
        content="Updated content",
        metadata={"new_key": "new_value"},
    )["results"]
    # /new_branch_id = update_resp["new_branch_id"]

    assert update_resp["message"], "No message returned after update"
    assert update_resp["metadata"], "No metadata returned after update"
    assert update_resp["id"], "No metadata returned after update"

    # Retrieve the conversation with the new branch
    updated_conv = client.conversations.retrieve(id=test_conversation)[
        "results"
    ]
    assert updated_conv, "No conversation returned after update"
    assert (
        updated_conv[0]["message"]["content"] == "Updated content"
    ), "Message content not updated"
    # found_updated = any(msg["id"] == new_message_id and msg["message"]["content"] == "Updated content" for msg in updated_conv)
    # assert found_updated, "Updated message not found in the new branch"


def test_update_non_existent_message(client, test_conversation):
    fake_msg_id = str(uuid.uuid4())
    with pytest.raises(FUSEException) as exc_info:
        client.conversations.update_message(
            id=test_conversation, message_id=fake_msg_id, content="Should fail"
        )
    assert (
        exc_info.value.status_code == 404
    ), "Wrong error code for updating non-existent message"


def test_add_message_with_empty_content(client, test_conversation):
    with pytest.raises(FUSEException) as exc_info:
        client.conversations.add_message(
            id=test_conversation,
            content="",  # empty content
            role="user",
        )
    # Check for 400 or a relevant error code depending on server validation
    assert (
        exc_info.value.status_code == 400
    ), "Wrong error code or no error for empty content message"


def test_add_message_invalid_role(client, test_conversation):
    with pytest.raises(FUSEException) as exc_info:
        client.conversations.add_message(
            id=test_conversation,
            content="Hello",
            role="invalid_role",
        )
    assert (
        exc_info.value.status_code == 400
    ), "Wrong error code or no error for invalid role"


def test_add_message_to_deleted_conversation(client):
    # Create a conversation and delete it
    conv_id = client.conversations.create()["results"]["id"]
    client.conversations.delete(id=conv_id)

    # Try adding a message to the deleted conversation
    with pytest.raises(FUSEException) as exc_info:
        client.conversations.add_message(
            id=conv_id,
            content="Should fail",
            role="user",
        )
    assert (
        exc_info.value.status_code == 404
    ), "Wrong error code for adding message to deleted conversation"


def test_update_message_with_additional_metadata(client, test_conversation):
    # Add a message with initial metadata
    msg_resp = client.conversations.add_message(
        id=test_conversation,
        content="Initial content",
        role="user",
        metadata={"initial_key": "initial_value"},
    )["results"]
    original_msg_id = msg_resp["id"]

    # Update the message with new content and additional metadata
    update_resp = client.conversations.update_message(
        id=test_conversation,
        message_id=original_msg_id,
        content="Updated content",
        metadata={"new_key": "new_value"},
    )["results"]

    # Retrieve the conversation from the new branch
    updated_conv = client.conversations.retrieve(id=test_conversation)[
        "results"
    ]

    # Find the updated message
    updated_message = next(
        (msg for msg in updated_conv if msg["id"] == original_msg_id), None
    )
    assert (
        updated_message is not None
    ), "Updated message not found in conversation"

    # Check that metadata includes old keys, new keys, and 'edited': True
    msg_metadata = updated_message["metadata"]
    assert (
        msg_metadata.get("initial_key") == "initial_value"
    ), "Old metadata not preserved"
    assert msg_metadata.get("new_key") == "new_value", "New metadata not added"
    assert (
        msg_metadata.get("edited") is True
    ), "'edited' flag not set in metadata"
    assert (
        updated_message["message"]["content"] == "Updated content"
    ), "Message content not updated"
