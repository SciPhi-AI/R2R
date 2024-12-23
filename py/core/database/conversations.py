import json
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException

from core.base import Handler, Message, R2RException
from shared.api.models.management.responses import (
    ConversationResponse,
    MessageResponse,
)

from .base import PostgresConnectionManager


class PostgresConversationsHandler(Handler):
    def __init__(
        self, project_name: str, connection_manager: PostgresConnectionManager
    ):
        self.project_name = project_name
        self.connection_manager = connection_manager

    async def create_tables(self):
        create_conversations_query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name("conversations")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            name TEXT
        );
        """

        create_messages_query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name("messages")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            conversation_id UUID NOT NULL,
            parent_id UUID,
            content JSONB,
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (conversation_id) REFERENCES {self._get_table_name("conversations")}(id),
            FOREIGN KEY (parent_id) REFERENCES {self._get_table_name("messages")}(id)
        );
        """
        await self.connection_manager.execute_query(create_conversations_query)
        await self.connection_manager.execute_query(create_messages_query)

    async def create_conversation(
        self,
        user_id: Optional[UUID] = None,
        name: Optional[str] = None,
    ) -> ConversationResponse:
        query = f"""
            INSERT INTO {self._get_table_name("conversations")} (user_id, name)
            VALUES ($1, $2)
            RETURNING id, extract(epoch from created_at) as created_at_epoch
        """
        try:
            result = await self.connection_manager.fetchrow_query(
                query, [user_id, name]
            )

            return ConversationResponse(
                id=result["id"],
                created_at=result["created_at_epoch"],
                user_id=user_id or None,
                name=name or None,
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create conversation: {str(e)}",
            ) from e

    async def get_conversations_overview(
        self,
        offset: int,
        limit: int,
        filter_user_ids: Optional[list[UUID]] = None,
        conversation_ids: Optional[list[UUID]] = None,
    ) -> dict[str, Any]:
        conditions = []
        params: list = []
        param_index = 1

        if filter_user_ids:
            conditions.append(
                f"""
                c.user_id IN (
                    SELECT id
                    FROM {self.project_name}.users
                    WHERE id = ANY(${param_index})
                )
            """
            )
            params.append(filter_user_ids)
            param_index += 1

        if conversation_ids:
            conditions.append(f"c.id = ANY(${param_index})")
            params.append(conversation_ids)
            param_index += 1

        where_clause = (
            "WHERE " + " AND ".join(conditions) if conditions else ""
        )

        query = f"""
            WITH conversation_overview AS (
                SELECT c.id,
                    extract(epoch from c.created_at) as created_at_epoch,
                    c.user_id,
                    c.name
                FROM {self._get_table_name("conversations")} c
                {where_clause}
            ),
            counted_overview AS (
                SELECT *,
                    COUNT(*) OVER() AS total_entries
                FROM conversation_overview
            )
            SELECT * FROM counted_overview
            ORDER BY created_at_epoch DESC
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            query += f" LIMIT ${param_index}"
            params.append(limit)

        results = await self.connection_manager.fetch_query(query, params)

        if not results:
            return {"results": [], "total_entries": 0}

        total_entries = results[0]["total_entries"]
        conversations = [
            {
                "id": str(row["id"]),
                "created_at": row["created_at_epoch"],
                "user_id": str(row["user_id"]) if row["user_id"] else None,
                "name": row["name"] or None,
            }
            for row in results
        ]

        return {"results": conversations, "total_entries": total_entries}

    async def add_message(
        self,
        conversation_id: UUID,
        content: Message,
        parent_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
    ) -> MessageResponse:
        # Check if conversation exists
        conv_check_query = f"""
            SELECT 1 FROM {self._get_table_name("conversations")}
            WHERE id = $1
        """
        conv_row = await self.connection_manager.fetchrow_query(
            conv_check_query, [conversation_id]
        )
        if not conv_row:
            raise R2RException(
                status_code=404,
                message=f"Conversation {conversation_id} not found.",
            )

        # Check parent message if provided
        if parent_id:
            parent_check_query = f"""
                SELECT 1 FROM {self._get_table_name("messages")}
                WHERE id = $1 AND conversation_id = $2
            """
            parent_row = await self.connection_manager.fetchrow_query(
                parent_check_query, [parent_id, conversation_id]
            )
            if not parent_row:
                raise R2RException(
                    status_code=404,
                    message=f"Parent message {parent_id} not found in conversation {conversation_id}.",
                )

        message_id = uuid4()
        content_str = json.dumps(content.model_dump())
        metadata_str = json.dumps(metadata or {})

        query = f"""
            INSERT INTO {self._get_table_name("messages")}
            (id, conversation_id, parent_id, content, created_at, metadata)
            VALUES ($1, $2, $3, $4::jsonb, NOW(), $5::jsonb)
            RETURNING id
        """
        inserted = await self.connection_manager.fetchrow_query(
            query,
            [
                message_id,
                conversation_id,
                parent_id,
                content_str,
                metadata_str,
            ],
        )
        if not inserted:
            raise R2RException(
                status_code=500, message="Failed to insert message."
            )

        return MessageResponse(id=message_id, message=content)

    async def edit_message(
        self,
        message_id: UUID,
        new_content: str | None = None,
        additional_metadata: dict | None = None,
    ) -> dict[str, Any]:
        # Get the original message
        query = f"""
            SELECT conversation_id, parent_id, content, metadata, created_at
            FROM {self._get_table_name("messages")}
            WHERE id = $1
        """
        row = await self.connection_manager.fetchrow_query(query, [message_id])
        if not row:
            raise R2RException(
                status_code=404,
                message=f"Message {message_id} not found.",
            )

        old_content = json.loads(row["content"])
        old_metadata = json.loads(row["metadata"])

        if new_content is not None:
            old_message = Message(**old_content)
            edited_message = Message(
                role=old_message.role,
                content=new_content,
                name=old_message.name,
                function_call=old_message.function_call,
                tool_calls=old_message.tool_calls,
            )
            content_to_save = edited_message.model_dump()
        else:
            content_to_save = old_content

        additional_metadata = additional_metadata or {}

        new_metadata = {
            **old_metadata,
            **additional_metadata,
            "edited": (
                True
                if new_content is not None
                else old_metadata.get("edited", False)
            ),
        }

        # Update message without changing the timestamp
        update_query = f"""
            UPDATE {self._get_table_name("messages")}
            SET content = $1::jsonb,
                metadata = $2::jsonb,
                created_at = $3
            WHERE id = $4
            RETURNING id
        """
        updated = await self.connection_manager.fetchrow_query(
            update_query,
            [
                json.dumps(content_to_save),
                json.dumps(new_metadata),
                row["created_at"],
                message_id,
            ],
        )
        if not updated:
            raise R2RException(
                status_code=500, message="Failed to update message."
            )

        return {
            "id": str(message_id),
            "message": (
                Message(**content_to_save)
                if isinstance(content_to_save, dict)
                else content_to_save
            ),
            "metadata": new_metadata,
        }

    async def update_message_metadata(
        self, message_id: UUID, metadata: dict
    ) -> None:
        # Fetch current metadata
        query = f"""
            SELECT metadata FROM {self._get_table_name("messages")}
            WHERE id = $1
        """
        row = await self.connection_manager.fetchrow_query(query, [message_id])
        if not row:
            raise R2RException(
                status_code=404, message=f"Message {message_id} not found."
            )

        current_metadata = json.loads(row["metadata"]) or {}
        updated_metadata = {**current_metadata, **metadata}

        update_query = f"""
            UPDATE {self._get_table_name("messages")}
            SET metadata = $1::jsonb
            WHERE id = $2
        """
        await self.connection_manager.execute_query(
            update_query, [json.dumps(updated_metadata), message_id]
        )

    async def get_conversation(
        self,
        conversation_id: UUID,
        filter_user_ids: Optional[list[UUID]] = None,
    ) -> list[MessageResponse]:
        conditions = ["c.id = $1"]
        params: list = [conversation_id]

        if filter_user_ids:
            param_index = 2
            conditions.append(
                f"""
                c.user_id IN (
                    SELECT id
                    FROM {self.project_name}.users
                    WHERE id = ANY(${param_index})
                )
            """
            )
            params.append(filter_user_ids)

        query = f"""
            SELECT c.id, extract(epoch from c.created_at) AS created_at_epoch
            FROM {self._get_table_name('conversations')} c
            WHERE {' AND '.join(conditions)}
        """

        conv_row = await self.connection_manager.fetchrow_query(query, params)
        if not conv_row:
            raise R2RException(
                status_code=404,
                message=f"Conversation {conversation_id} not found.",
            )

        # Retrieve messages in chronological order
        msg_query = f"""
            SELECT id, content, metadata
            FROM {self._get_table_name("messages")}
            WHERE conversation_id = $1
            ORDER BY created_at ASC
        """
        results = await self.connection_manager.fetch_query(
            msg_query, [conversation_id]
        )

        return [
            MessageResponse(
                id=row["id"],
                message=Message(**json.loads(row["content"])),
                metadata=json.loads(row["metadata"]),
            )
            for row in results
        ]

    async def update_conversation(
        self, conversation_id: UUID, name: str
    ) -> ConversationResponse:
        try:
            # Check if conversation exists
            conv_query = f"SELECT 1 FROM {self._get_table_name('conversations')} WHERE id = $1"
            conv_row = await self.connection_manager.fetchrow_query(
                conv_query, [conversation_id]
            )
            if not conv_row:
                raise R2RException(
                    status_code=404,
                    message=f"Conversation {conversation_id} not found.",
                )

            update_query = f"""
            UPDATE {self._get_table_name('conversations')}
            SET name = $1 WHERE id = $2
            RETURNING user_id, extract(epoch from created_at) as created_at_epoch
            """
            updated_row = await self.connection_manager.fetchrow_query(
                update_query, [name, conversation_id]
            )
            return ConversationResponse(
                id=conversation_id,
                created_at=updated_row["created_at_epoch"],
                user_id=updated_row["user_id"] or None,
                name=name,
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update conversation: {str(e)}",
            ) from e

    async def delete_conversation(
        self,
        conversation_id: UUID,
        filter_user_ids: Optional[list[UUID]] = None,
    ) -> None:
        conditions = ["c.id = $1"]
        params: list = [conversation_id]

        if filter_user_ids:
            param_index = 2
            conditions.append(
                f"""
                c.user_id IN (
                    SELECT id
                    FROM {self.project_name}.users
                    WHERE id = ANY(${param_index})
                )
            """
            )
            params.append(filter_user_ids)

        conv_query = f"""
            SELECT 1
            FROM {self._get_table_name('conversations')} c
            WHERE {' AND '.join(conditions)}
        """
        conv_row = await self.connection_manager.fetchrow_query(
            conv_query, params
        )
        if not conv_row:
            raise R2RException(
                status_code=404,
                message=f"Conversation {conversation_id} not found.",
            )

        # Delete all messages
        del_messages_query = f"DELETE FROM {self._get_table_name('messages')} WHERE conversation_id = $1"
        await self.connection_manager.execute_query(
            del_messages_query, [conversation_id]
        )

        # Delete conversation
        del_conv_query = f"DELETE FROM {self._get_table_name('conversations')} WHERE id = $1"
        await self.connection_manager.execute_query(
            del_conv_query, [conversation_id]
        )
