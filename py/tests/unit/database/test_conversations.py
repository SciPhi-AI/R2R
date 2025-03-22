import uuid

import pytest

from core.base import Message, R2RException
from shared.api.models.management.responses import (
    ConversationResponse,
    MessageResponse,
)


@pytest.mark.asyncio
async def test_create_conversation(conversations_handler):
    resp = await conversations_handler.create_conversation()
    assert isinstance(resp, ConversationResponse)
    assert resp.id is not None
    assert resp.created_at is not None


@pytest.mark.asyncio
async def test_create_conversation_with_user_and_name(conversations_handler):
    user_id = uuid.uuid4()
    resp = await conversations_handler.create_conversation(user_id=user_id,
                                                           name="Test Conv")
    assert resp.id is not None
    assert resp.created_at is not None
    # There's no direct field for user_id in ConversationResponse,
    # but we can verify by fetch:
    # Just trust it for now since the handler doesn't return user_id directly.


@pytest.mark.asyncio
async def test_add_message(conversations_handler):
    conv = await conversations_handler.create_conversation()
    conv_id = conv.id

    msg = Message(role="user", content="Hello!")
    resp = await conversations_handler.add_message(conv_id, msg)
    assert isinstance(resp, MessageResponse)
    assert resp.id is not None
    assert resp.message.content == "Hello!"


@pytest.mark.asyncio
async def test_add_message_with_parent(conversations_handler):
    conv = await conversations_handler.create_conversation()
    conv_id = conv.id

    parent_msg = Message(role="user", content="Parent message")
    parent_resp = await conversations_handler.add_message(conv_id, parent_msg)
    parent_id = parent_resp.id

    child_msg = Message(role="assistant", content="Child reply")
    child_resp = await conversations_handler.add_message(conv_id,
                                                         child_msg,
                                                         parent_id=parent_id)
    assert child_resp.id is not None
    assert child_resp.message.content == "Child reply"


@pytest.mark.asyncio
async def test_edit_message(conversations_handler):
    conv = await conversations_handler.create_conversation()
    conv_id = conv.id

    original_msg = Message(role="user", content="Original")
    resp = await conversations_handler.add_message(conv_id, original_msg)
    msg_id = resp.id

    updated = await conversations_handler.edit_message(msg_id,
                                                       "Edited content")
    assert updated["message"].content == "Edited content"
    assert updated["metadata"]["edited"] is True


@pytest.mark.asyncio
async def test_update_message_metadata(conversations_handler):
    conv = await conversations_handler.create_conversation()
    conv_id = conv.id

    msg = Message(role="user", content="Meta-test")
    resp = await conversations_handler.add_message(conv_id, msg)
    msg_id = resp.id

    await conversations_handler.update_message_metadata(
        msg_id, {"test_key": "test_value"})

    # Verify metadata updated
    full_conversation = await conversations_handler.get_conversation(conv_id)
    for m in full_conversation:
        if m.id == str(msg_id):
            assert m.metadata["test_key"] == "test_value"
            break


@pytest.mark.asyncio
async def test_get_conversation(conversations_handler):
    conv = await conversations_handler.create_conversation()
    conv_id = conv.id

    msg1 = Message(role="user", content="Msg1")
    msg2 = Message(role="assistant", content="Msg2")

    await conversations_handler.add_message(conv_id, msg1)
    await conversations_handler.add_message(conv_id, msg2)

    messages = await conversations_handler.get_conversation(conv_id)
    assert len(messages) == 2
    assert messages[0].message.content == "Msg1"
    assert messages[1].message.content == "Msg2"


@pytest.mark.asyncio
async def test_delete_conversation(conversations_handler):
    conv = await conversations_handler.create_conversation()
    conv_id = conv.id

    msg = Message(role="user", content="To be deleted")
    await conversations_handler.add_message(conv_id, msg)

    await conversations_handler.delete_conversation(conv_id)

    with pytest.raises(R2RException) as exc:
        await conversations_handler.get_conversation(conv_id)
    assert exc.value.status_code == 404, (
        "Conversation should be deleted and not found")
