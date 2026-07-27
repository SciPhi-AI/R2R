from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from core.base import Message, R2RException
from core.main.api.v3.conversations_router import ConversationsRouter
from core.main.services.management_service import ManagementService
from core.providers.database.conversations import PostgresConversationsHandler


def _route_endpoint(router, path, method="POST"):
    return next(
        route.endpoint
        for route in router.router.routes
        if route.path == path and method in route.methods
    )


@pytest.fixture
def conversations_router():
    providers = MagicMock()
    providers.auth.auth_wrapper.return_value = lambda: None
    services = MagicMock()
    services.management.update_conversation = AsyncMock(return_value=None)
    services.management.add_message = AsyncMock(return_value=None)
    services.management.edit_message = AsyncMock(return_value=None)
    return ConversationsRouter(providers, services, MagicMock())


@pytest.mark.asyncio
async def test_conversation_write_routes_pass_requesting_user(
    conversations_router,
):
    user_id = uuid4()
    auth_user = SimpleNamespace(id=user_id, is_superuser=False)
    conversation_id = uuid4()
    message_id = uuid4()

    await _route_endpoint(conversations_router, "/conversations/{id}")(
        id=conversation_id,
        name="Renamed",
        auth_user=auth_user,
    )
    await _route_endpoint(
        conversations_router, "/conversations/{id}/messages"
    )(
        id=conversation_id,
        content="Hello",
        role="user",
        parent_id=None,
        metadata=None,
        auth_user=auth_user,
    )
    await _route_endpoint(
        conversations_router,
        "/conversations/{id}/messages/{message_id}",
    )(
        id=conversation_id,
        message_id=message_id,
        content="Updated",
        metadata=None,
        auth_user=auth_user,
    )

    conversations_router.services.management.update_conversation.assert_awaited_once_with(
        conversation_id=conversation_id,
        name="Renamed",
        user_ids=[user_id],
    )
    conversations_router.services.management.add_message.assert_awaited_once_with(
        conversation_id=conversation_id,
        content=Message(role="user", content="Hello"),
        parent_id=None,
        metadata=None,
        user_ids=[user_id],
    )
    conversations_router.services.management.edit_message.assert_awaited_once_with(
        conversation_id=conversation_id,
        message_id=message_id,
        new_content="Updated",
        additional_metadata=None,
        user_ids=[user_id],
    )


@pytest.mark.asyncio
async def test_conversation_write_routes_do_not_filter_superusers(
    conversations_router,
):
    conversation_id = uuid4()
    auth_user = SimpleNamespace(id=uuid4(), is_superuser=True)

    await _route_endpoint(conversations_router, "/conversations/{id}")(
        id=conversation_id,
        name="Renamed",
        auth_user=auth_user,
    )

    conversations_router.services.management.update_conversation.assert_awaited_once_with(
        conversation_id=conversation_id,
        name="Renamed",
        user_ids=None,
    )


@pytest.mark.asyncio
async def test_management_service_passes_ownership_filters():
    providers = MagicMock()
    handler = providers.database.conversations_handler
    handler.update_conversation = AsyncMock(return_value=None)
    handler.add_message = AsyncMock(return_value=None)
    handler.edit_message = AsyncMock(return_value=None)
    service = ManagementService(MagicMock(), providers)
    conversation_id = uuid4()
    message_id = uuid4()
    user_ids = [uuid4()]
    message = Message(role="user", content="Hello")

    await service.update_conversation(
        conversation_id, "Renamed", user_ids=user_ids
    )
    await service.add_message(conversation_id, message, user_ids=user_ids)
    await service.edit_message(
        message_id,
        conversation_id=conversation_id,
        user_ids=user_ids,
    )

    handler.update_conversation.assert_awaited_once_with(
        conversation_id=conversation_id,
        name="Renamed",
        filter_user_ids=user_ids,
    )
    handler.add_message.assert_awaited_once_with(
        conversation_id=conversation_id,
        content=message,
        parent_id=None,
        metadata=None,
        filter_user_ids=user_ids,
    )
    handler.edit_message.assert_awaited_once_with(
        message_id=message_id,
        new_content=None,
        additional_metadata={},
        conversation_id=conversation_id,
        filter_user_ids=user_ids,
    )


@pytest.fixture
def conversations_handler():
    connection_manager = AsyncMock()
    return PostgresConversationsHandler("test_project", connection_manager)


@pytest.mark.asyncio
async def test_add_message_rejects_unowned_conversation(
    conversations_handler,
):
    conversation_id = uuid4()
    user_ids = [uuid4()]
    conversations_handler.connection_manager.fetchrow_query.return_value = None

    with pytest.raises(R2RException) as exc_info:
        await conversations_handler.add_message(
            conversation_id,
            Message(role="user", content="Hello"),
            filter_user_ids=user_ids,
        )

    assert exc_info.value.status_code == 404
    query, params = (
        conversations_handler.connection_manager.fetchrow_query.call_args.args
    )
    assert "user_id = ANY($2)" in query
    assert params == [conversation_id, user_ids]


@pytest.mark.asyncio
async def test_update_conversation_rejects_unowned_conversation(
    conversations_handler,
):
    conversation_id = uuid4()
    user_ids = [uuid4()]
    conversations_handler.connection_manager.fetchrow_query.return_value = None

    with pytest.raises(R2RException) as exc_info:
        await conversations_handler.update_conversation(
            conversation_id,
            "Renamed",
            filter_user_ids=user_ids,
        )

    assert exc_info.value.status_code == 404
    query, params = (
        conversations_handler.connection_manager.fetchrow_query.call_args.args
    )
    assert "user_id = ANY($2)" in query
    assert params == [conversation_id, user_ids]


@pytest.mark.asyncio
async def test_edit_message_rejects_unowned_conversation(
    conversations_handler,
):
    conversation_id = uuid4()
    message_id = uuid4()
    user_ids = [uuid4()]
    conversations_handler.connection_manager.fetchrow_query.return_value = None

    with pytest.raises(R2RException) as exc_info:
        await conversations_handler.edit_message(
            message_id,
            conversation_id=conversation_id,
            filter_user_ids=user_ids,
        )

    assert exc_info.value.status_code == 404
    query, params = (
        conversations_handler.connection_manager.fetchrow_query.call_args.args
    )
    assert "m.conversation_id = $2" in query
    assert "c.user_id = ANY($3)" in query
    assert params == [message_id, conversation_id, user_ids]
