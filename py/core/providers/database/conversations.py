import csv
import json
import logging
import tempfile
from datetime import datetime
from typing import IO, Any, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException

from core.base import Handler, Message, R2RException
from shared.api.models.management.responses import (
    ConversationResponse,
    MessageResponse,
)

from .base import PostgresConnectionManager

logger = logging.getLogger(__name__)


def _validate_image_size(
    message: Message, max_size_bytes: int = 5 * 1024 * 1024
) -> None:
    """
    Validates that images in a message don't exceed the maximum allowed size.

    Args:
        message: Message object to validate
        max_size_bytes: Maximum allowed size for base64-encoded images (default: 5MB)

    Raises:
        R2RException: If image is too large
    """
    if (
        hasattr(message, "image_data")
        and message.image_data
        and "data" in message.image_data
    ):
        base64_data = message.image_data["data"]

        # Calculate approximate decoded size (base64 increases size by ~33%)
        # The formula is: decoded_size = encoded_size * 3/4
        estimated_size_bytes = len(base64_data) * 0.75

        if estimated_size_bytes > max_size_bytes:
            raise R2RException(
                status_code=413,  # Payload Too Large
                message=f"Image too large: {estimated_size_bytes / 1024 / 1024:.2f}MB exceeds the maximum allowed size of {max_size_bytes / 1024 / 1024:.2f}MB",
            )


def _json_default(obj: Any) -> str:
    """Default handler for objects not serializable by the standard json
    encoder."""
    if isinstance(obj, datetime):
        # Return ISO8601 string
        return obj.isoformat()
    elif isinstance(obj, UUID):
        # Convert UUID to string
        return str(obj)
    # If you have other special types, handle them here...
    # e.g. decimal.Decimal -> str(obj)

    # If we get here, raise an error or just default to string:
    raise TypeError(f"Type {type(obj)} not serializable")


def safe_dumps(obj: Any) -> str:
    """Wrap `json.dumps` with a default that serializes UUID and datetime."""
    return json.dumps(obj, default=_json_default)


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
            conditions.append(f"""
                c.user_id IN (
                    SELECT id
                    FROM {self.project_name}.users
                    WHERE id = ANY(${param_index})
                )
            """)
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
        max_image_size_bytes: int = 5 * 1024 * 1024,  # 5MB default
    ) -> MessageResponse:
        # Validate image size
        try:
            _validate_image_size(content, max_image_size_bytes)
        except R2RException:
            # Re-raise validation exceptions
            raise
        except Exception as e:
            # Handle unexpected errors during validation
            logger.error(f"Error validating image: {str(e)}")
            raise R2RException(
                status_code=400, message=f"Invalid image data: {str(e)}"
            ) from e

        # 1) Validate that conversation and parent exist (existing code)
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

        # 2) Add image info to metadata for tracking/analytics if images are present
        metadata = metadata or {}
        if hasattr(content, "image_url") and content.image_url:
            metadata["has_image"] = True
            metadata["image_type"] = "url"
        elif hasattr(content, "image_data") and content.image_data:
            metadata["has_image"] = True
            metadata["image_type"] = "base64"
            # Don't store the actual base64 data in metadata as it would be redundant

        # 3) Convert the content & metadata to JSON strings
        message_id = uuid4()
        # Using safe_dumps to handle any type of serialization
        content_str = safe_dumps(content.model_dump())
        metadata_str = safe_dumps(metadata)

        # 4) Insert the message (existing code)
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
                # Preserve image content if it exists
                image_url=getattr(old_message, "image_url", None),
                image_data=getattr(old_message, "image_data", None),
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
        # Existing validation code remains the same
        conditions = ["c.id = $1"]
        params: list = [conversation_id]

        if filter_user_ids:
            param_index = 2
            conditions.append(f"""
                c.user_id IN (
                    SELECT id
                    FROM {self.project_name}.users
                    WHERE id = ANY(${param_index})
                )
            """)
            params.append(filter_user_ids)

        query = f"""
            SELECT c.id, extract(epoch from c.created_at) AS created_at_epoch
            FROM {self._get_table_name("conversations")} c
            WHERE {" AND ".join(conditions)}
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

        response_messages = []
        for row in results:
            try:
                # Parse the message content
                content_json = json.loads(row["content"])
                # Create a Message object with the parsed content
                message = Message(**content_json)
                # Create a MessageResponse
                response_messages.append(
                    MessageResponse(
                        id=row["id"],
                        message=message,
                        metadata=json.loads(row["metadata"]),
                    )
                )
            except Exception as e:
                # If there's an error parsing the message (e.g., due to version mismatch),
                # log it and create a fallback message
                logger.warning(f"Error parsing message {row['id']}: {str(e)}")
                fallback_content = content_json.get(
                    "content", "Message could not be loaded"
                )
                fallback_role = content_json.get("role", "assistant")

                # Create a basic fallback message
                fallback_message = Message(
                    role=fallback_role,
                    content=f"[Message format incompatible: {fallback_content}]",
                )

                response_messages.append(
                    MessageResponse(
                        id=row["id"],
                        message=fallback_message,
                        metadata=json.loads(row["metadata"]),
                    )
                )

        return response_messages

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
            UPDATE {self._get_table_name("conversations")}
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
            conditions.append(f"""
                c.user_id IN (
                    SELECT id
                    FROM {self.project_name}.users
                    WHERE id = ANY(${param_index})
                )
            """)
            params.append(filter_user_ids)

        conv_query = f"""
            SELECT 1
            FROM {self._get_table_name("conversations")} c
            WHERE {" AND ".join(conditions)}
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

    async def export_conversations_to_csv(
        self,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        """Creates a CSV file from the PostgreSQL data and returns the path to
        the temp file."""
        valid_columns = {
            "id",
            "user_id",
            "created_at",
            "name",
        }

        if not columns:
            columns = list(valid_columns)
        elif invalid_cols := set(columns) - valid_columns:
            raise ValueError(f"Invalid columns: {invalid_cols}")

        select_stmt = f"""
            SELECT
                id::text,
                user_id::text,
                to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                name
            FROM {self._get_table_name("conversations")}
        """

        conditions = []
        params: list[Any] = []
        param_index = 1

        if filters:
            for field, value in filters.items():
                if field not in valid_columns:
                    continue

                if isinstance(value, dict):
                    for op, val in value.items():
                        if op == "$eq":
                            conditions.append(f"{field} = ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$gt":
                            conditions.append(f"{field} > ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$lt":
                            conditions.append(f"{field} < ${param_index}")
                            params.append(val)
                            param_index += 1
                else:
                    # Direct equality
                    conditions.append(f"{field} = ${param_index}")
                    params.append(value)
                    param_index += 1

        if conditions:
            select_stmt = f"{select_stmt} WHERE {' AND '.join(conditions)}"

        select_stmt = f"{select_stmt} ORDER BY created_at DESC"

        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", delete=True, suffix=".csv"
            )
            writer = csv.writer(temp_file, quoting=csv.QUOTE_ALL)

            async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
                async with conn.transaction():
                    cursor = await conn.cursor(select_stmt, *params)

                    if include_header:
                        writer.writerow(columns)

                    chunk_size = 1000
                    while True:
                        rows = await cursor.fetch(chunk_size)
                        if not rows:
                            break
                        for row in rows:
                            row_dict = {
                                "id": row[0],
                                "user_id": row[1],
                                "created_at": row[2],
                                "name": row[3],
                            }
                            writer.writerow([row_dict[col] for col in columns])

            temp_file.flush()
            return temp_file.name, temp_file

        except Exception as e:
            if temp_file:
                temp_file.close()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to export data: {str(e)}",
            ) from e

    async def export_messages_to_csv(
        self,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
        handle_images: str = "metadata_only",  # Options: "full", "metadata_only", "exclude"
    ) -> tuple[str, IO]:
        """
        Creates a CSV file from the PostgreSQL data and returns the path to the temp file.

        Args:
            columns: List of columns to include in export
            filters: Filter criteria for messages
            include_header: Whether to include header row
            handle_images: How to handle image data in exports:
                - "full": Include complete image data (warning: may create large files)
                - "metadata_only": Replace image data with metadata only
                - "exclude": Remove image data completely
        """
        valid_columns = {
            "id",
            "conversation_id",
            "parent_id",
            "content",
            "metadata",
            "created_at",
            "has_image",  # New virtual column to indicate image presence
        }

        if not columns:
            columns = list(valid_columns - {"has_image"})
        elif invalid_cols := set(columns) - valid_columns:
            raise ValueError(f"Invalid columns: {invalid_cols}")

        # Add virtual column for image presence
        virtual_columns = []
        has_image_column = False

        if "has_image" in columns:
            virtual_columns.append(
                "(content->>'image_url' IS NOT NULL OR content->>'image_data' IS NOT NULL) as has_image"
            )
            columns.remove("has_image")
            has_image_column = True

        select_stmt = f"""
            SELECT
                id::text,
                conversation_id::text,
                parent_id::text,
                content::text,
                metadata::text,
                to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
                {", " + ", ".join(virtual_columns) if virtual_columns else ""}
            FROM {self._get_table_name("messages")}
        """

        # Keep existing filter conditions setup
        conditions = []
        params: list[Any] = []
        param_index = 1

        if filters:
            for field, value in filters.items():
                if field not in valid_columns or field == "has_image":
                    continue

                if isinstance(value, dict):
                    for op, val in value.items():
                        if op == "$eq":
                            conditions.append(f"{field} = ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$gt":
                            conditions.append(f"{field} > ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$lt":
                            conditions.append(f"{field} < ${param_index}")
                            params.append(val)
                            param_index += 1
                else:
                    conditions.append(f"{field} = ${param_index}")
                    params.append(value)
                    param_index += 1

        # Special filter for has_image
        if filters and "has_image" in filters:
            if filters["has_image"]:
                conditions.append(
                    "(content->>'image_url' IS NOT NULL OR content->>'image_data' IS NOT NULL)"
                )

        if conditions:
            select_stmt = f"{select_stmt} WHERE {' AND '.join(conditions)}"

        select_stmt = f"{select_stmt} ORDER BY created_at DESC"

        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", delete=True, suffix=".csv"
            )
            writer = csv.writer(temp_file, quoting=csv.QUOTE_ALL)

            # Prepare export columns
            export_columns = list(columns)
            if has_image_column:
                export_columns.append("has_image")

            if include_header:
                writer.writerow(export_columns)

            async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
                async with conn.transaction():
                    cursor = await conn.cursor(select_stmt, *params)

                    chunk_size = 1000
                    while True:
                        rows = await cursor.fetch(chunk_size)
                        if not rows:
                            break
                        for row in rows:
                            row_dict = {
                                "id": row[0],
                                "conversation_id": row[1],
                                "parent_id": row[2],
                                "content": row[3],
                                "metadata": row[4],
                                "created_at": row[5],
                            }

                            # Add virtual column if present
                            if has_image_column:
                                row_dict["has_image"] = (
                                    "true" if row[6] else "false"
                                )

                            # Process image data based on handle_images setting
                            if (
                                "content" in columns
                                and handle_images != "full"
                            ):
                                try:
                                    content_json = json.loads(
                                        row_dict["content"]
                                    )

                                    if (
                                        "image_data" in content_json
                                        and content_json["image_data"]
                                    ):
                                        media_type = content_json[
                                            "image_data"
                                        ].get("media_type", "image/jpeg")

                                        if handle_images == "metadata_only":
                                            content_json["image_data"] = {
                                                "media_type": media_type,
                                                "data": "[BASE64_DATA_EXCLUDED_FROM_EXPORT]",
                                            }
                                        elif handle_images == "exclude":
                                            content_json.pop(
                                                "image_data", None
                                            )

                                    row_dict["content"] = json.dumps(
                                        content_json
                                    )
                                except (json.JSONDecodeError, TypeError) as e:
                                    logger.warning(
                                        f"Error processing message content for export: {e}"
                                    )

                            writer.writerow(
                                [row_dict[col] for col in export_columns]
                            )

            temp_file.flush()
            return temp_file.name, temp_file

        except Exception as e:
            if temp_file:
                temp_file.close()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to export data: {str(e)}",
            ) from e
