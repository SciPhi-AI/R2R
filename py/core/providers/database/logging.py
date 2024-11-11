import json
import os
from typing import Any, Optional, Tuple, Union
from uuid import UUID

from core.base import LoggingHandler, Message
from core.base.logger.base import RunInfoLog, RunType

from .base import PostgresConnectionManager


class PostgresLoggingHandler(LoggingHandler):
    """PostgreSQL implementation of the LoggingHandler using ConnectionManager."""

    LOG_TABLE = "logs"
    LOG_INFO_TABLE = "log_info"

    def __init__(
        self, project_name: str, connection_manager: PostgresConnectionManager
    ):
        super().__init__(project_name, connection_manager)

    async def create_tables(self) -> None:
        """Create necessary tables for logging and conversation management."""
        # Create schema and base logging tables
        query = f"""
        CREATE SCHEMA IF NOT EXISTS {self.project_name};

        CREATE TABLE IF NOT EXISTS {self._get_table_name(self.LOG_TABLE)} (
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            run_id UUID,
            key TEXT,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS {self._get_table_name(self.LOG_INFO_TABLE)} (
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            run_id UUID UNIQUE,
            run_type TEXT,
            user_id UUID
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY,
            conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
            parent_id UUID REFERENCES messages(id),
            content JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB
        );

        CREATE TABLE IF NOT EXISTS branches (
            id UUID PRIMARY KEY,
            conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
            branch_point_id UUID REFERENCES messages(id),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS message_branches (
            message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
            branch_id UUID REFERENCES branches(id) ON DELETE CASCADE,
            PRIMARY KEY (message_id, branch_id)
        );

        CREATE INDEX IF NOT EXISTS idx_{self.project_name}_{self.LOG_TABLE}_run_id
        ON {self._get_table_name(self.LOG_TABLE)}(run_id);

        CREATE INDEX IF NOT EXISTS idx_{self.project_name}_{self.LOG_INFO_TABLE}_run_id
        ON {self._get_table_name(self.LOG_INFO_TABLE)}(run_id);

        CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
        ON messages(conversation_id);

        CREATE INDEX IF NOT EXISTS idx_messages_parent_id
        ON messages(parent_id);

        CREATE INDEX IF NOT EXISTS idx_branches_conversation_id
        ON branches(conversation_id);

        CREATE INDEX IF NOT EXISTS idx_message_branches_branch_id
        ON message_branches(branch_id);

        CREATE INDEX IF NOT EXISTS idx_message_branches_message_id
        ON message_branches(message_id);
        """
        await self.connection_manager.execute_query(query)

    async def log(self, run_id: UUID, key: str, value: str) -> None:
        """Log a key-value pair for a specific run."""
        query = f"""
        INSERT INTO {self._get_table_name(self.LOG_TABLE)}
        (run_id, key, value)
        VALUES ($1, $2, $3)
        """
        await self.connection_manager.execute_query(
            query, [run_id, key, value]
        )

    async def info_log(
        self, run_id: UUID, run_type: RunType, user_id: UUID
    ) -> None:
        """Log run information."""
        query = f"""
        INSERT INTO {self._get_table_name(self.LOG_INFO_TABLE)}
        (run_id, run_type, user_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (run_id) DO UPDATE SET
            timestamp = CURRENT_TIMESTAMP,
            run_type = EXCLUDED.run_type,
            user_id = EXCLUDED.user_id
        """
        await self.connection_manager.execute_query(
            query, [run_id, run_type, user_id]
        )

    async def get_logs(
        self, run_ids: list[UUID], limit_per_run: int = 10
    ) -> list[dict[str, Any]]:
        """Retrieve logs for specified run IDs."""
        if not run_ids:
            raise ValueError("No run ids provided")

        query = f"""
        WITH ranked_logs AS (
            SELECT
                run_id,
                key,
                value,
                timestamp,
                ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY timestamp DESC) as rn
            FROM {self._get_table_name(self.LOG_TABLE)}
            WHERE run_id = ANY($1)
        )
        SELECT run_id, key, value, timestamp
        FROM ranked_logs
        WHERE rn <= $2
        ORDER BY timestamp DESC
        """
        rows = await self.connection_manager.fetch_query(
            query, [run_ids, limit_per_run]
        )
        return [dict(row) for row in rows]

    async def get_info_logs(
        self,
        offset: int,
        limit: int,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        """Retrieve run information logs with filtering options."""
        conditions = []
        params: list[Any] = []

        query = f"""
        SELECT run_id, run_type, timestamp, user_id
        FROM {self._get_table_name(self.LOG_INFO_TABLE)}
        """

        if run_type_filter:
            conditions.append(f"run_type = ${len(params) + 1}")
            params.append(run_type_filter)

        if user_ids:
            conditions.append(f"user_id = ANY(${len(params) + 1})")
            params.append(user_ids)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY timestamp DESC OFFSET ${len(params) + 1} LIMIT ${len(params) + 2}"
        params.extend([offset, limit])

        rows = await self.connection_manager.fetch_query(query, params)
        return [
            RunInfoLog(
                run_id=row["run_id"],
                run_type=row["run_type"],
                timestamp=row["timestamp"],
                user_id=row["user_id"],
            )
            for row in rows
        ]

    async def create_conversation(self) -> str:
        """Create a new conversation and return its ID."""
        query = """
        INSERT INTO conversations (id)
        VALUES ($1)
        RETURNING id
        """
        conversation_id = UUID(bytes=os.urandom(16))
        result = await self.connection_manager.fetchrow_query(
            query, [conversation_id]
        )
        return str(result["id"])

    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all associated data."""
        query = "DELETE FROM conversations WHERE id = $1"
        await self.connection_manager.execute_query(
            query, [UUID(conversation_id)]
        )

    async def get_conversations(
        self,
        offset: int,
        limit: int,
        conversation_ids: Optional[list[UUID]] = None,
    ) -> dict[str, Union[list[dict], int]]:
        """Get an overview of conversations with pagination."""
        query = """
        WITH conversation_overview AS (
            SELECT c.id, c.created_at
            FROM conversations c
            {where_clause}
        ),
        counted_overview AS (
            SELECT *, COUNT(*) OVER() AS total_entries
            FROM conversation_overview
        )
        SELECT * FROM counted_overview
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """

        where_clause = "WHERE c.id = ANY($3)" if conversation_ids else ""
        query = query.format(where_clause=where_clause)

        params = [limit if limit != -1 else None, offset]
        if conversation_ids:  # type: ignore
            params.append(conversation_ids)  # type: ignore

        rows = await self.connection_manager.fetch_query(query, params)

        if not rows:
            return {"results": [], "total_entries": 0}

        conversations = [
            {
                "conversation_id": str(row["id"]),
                "created_at": row["created_at"].timestamp(),
            }
            for row in rows
        ]

        total_entries = rows[0]["total_entries"] if rows else 0
        return {"results": conversations, "total_entries": total_entries}

    async def add_message(
        self,
        conversation_id: str,
        content: Message,
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Add a message to a conversation."""
        message_id = UUID(bytes=os.urandom(16))

        async def transaction():
            # Insert message
            message_query = """
            INSERT INTO messages (id, conversation_id, parent_id, content, metadata)
            VALUES ($1, $2, $3, $4, $5)
            """
            await self.connection_manager.execute_query(
                message_query,
                [
                    message_id,
                    UUID(conversation_id),
                    UUID(parent_id) if parent_id else None,
                    json.loads(content.json()),
                    metadata or {},
                ],
            )

            if parent_id:
                # Copy branch associations from parent
                branch_query = """
                INSERT INTO message_branches (message_id, branch_id)
                SELECT $1, branch_id FROM message_branches WHERE message_id = $2
                """
                await self.connection_manager.execute_query(
                    branch_query, [message_id, UUID(parent_id)]
                )
            else:
                # Get or create default branch
                branch_query = """
                SELECT id FROM branches
                WHERE conversation_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """
                branch_row = await self.connection_manager.fetchrow_query(
                    branch_query, [UUID(conversation_id)]
                )

                branch_id = (
                    branch_row["id"]
                    if branch_row
                    else UUID(bytes=os.urandom(16))
                )
                if not branch_row:
                    create_branch_query = """
                    INSERT INTO branches (id, conversation_id, branch_point_id)
                    VALUES ($1, $2, NULL)
                    """
                    await self.connection_manager.execute_query(
                        create_branch_query, [branch_id, UUID(conversation_id)]
                    )

                link_branch_query = """
                INSERT INTO message_branches (message_id, branch_id)
                VALUES ($1, $2)
                """
                await self.connection_manager.execute_query(
                    link_branch_query, [message_id, branch_id]
                )

        await self.connection_manager.execute_query(
            "BEGIN", isolation_level="serializable"
        )
        try:
            await transaction()
            await self.connection_manager.execute_query("COMMIT")
        except Exception as e:
            await self.connection_manager.execute_query("ROLLBACK")
            raise e

        return str(message_id)

    async def get_conversation(
        self, conversation_id: str, branch_id: Optional[str] = None
    ) -> list[Tuple[str, Message]]:
        """Retrieve all messages in a conversation branch."""
        if not branch_id:
            # Get the most recent branch
            get_branch_query = """
                SELECT id FROM branches
                WHERE conversation_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """
            row = await self.connection_manager.fetchrow_query(
                get_branch_query, [UUID(conversation_id)]
            )
            branch_id = str(row["id"]) if row else None

        if not branch_id:
            return []

        query = """
            WITH RECURSIVE branch_messages AS (
                SELECT m.id, m.content, m.parent_id, 0 as depth, m.created_at
                FROM messages m
                JOIN message_branches mb ON m.id = mb.message_id
                WHERE mb.branch_id = $1 AND m.parent_id IS NULL
                UNION ALL
                SELECT m.id, m.content, m.parent_id, bm.depth + 1, m.created_at
                FROM messages m
                JOIN message_branches mb ON m.id = mb.message_id
                JOIN branch_messages bm ON m.parent_id = bm.id
                WHERE mb.branch_id = $1
            )
            SELECT id, content
            FROM branch_messages
            ORDER BY created_at ASC
            """
        rows = await self.connection_manager.fetch_query(
            query, [UUID(branch_id)]
        )

        return [
            (str(row["id"]), Message.parse_raw(json.dumps(row["content"])))
            for row in rows
        ]

    async def get_branches(self, conversation_id: str) -> list[dict]:
        """Get an overview of all branches in a conversation."""
        query = """
        SELECT b.id, b.branch_point_id, m.content, b.created_at
        FROM branches b
        LEFT JOIN messages m ON b.branch_point_id = m.id
        WHERE b.conversation_id = $1
        ORDER BY b.created_at
        """
        rows = await self.connection_manager.fetch_query(
            query, [UUID(conversation_id)]
        )

        return [
            {
                "branch_id": str(row["id"]),
                "branch_point_id": (
                    str(row["branch_point_id"])
                    if row["branch_point_id"]
                    else None
                ),
                "content": row["content"],
                "created_at": row["created_at"].timestamp(),
            }
            for row in rows
        ]

    async def edit_message(
        self, message_id: str, new_content: str
    ) -> Tuple[str, str]:
        """Edit an existing message and return new message ID and branch ID."""
        new_message_id = UUID(bytes=os.urandom(16))
        new_branch_id = UUID(bytes=os.urandom(16))

        async def transaction():
            # Get original message details
            get_message_query = """
            SELECT conversation_id, parent_id, content
            FROM messages WHERE id = $1
            """
            row = await self.connection_manager.fetchrow_query(
                get_message_query, [UUID(message_id)]
            )

            if not row:
                raise ValueError(f"Message {message_id} not found")

            conversation_id = row["conversation_id"]
            parent_id = row["parent_id"]
            old_message = Message.parse_raw(json.dumps(row["content"]))

            # Create edited message
            edited_message = Message(
                role=old_message.role,
                content=new_content,
                name=old_message.name,
                function_call=old_message.function_call,
                tool_calls=old_message.tool_calls,
            )

            # Create new branch
            create_branch_query = """
            INSERT INTO branches (id, conversation_id, branch_point_id)
            VALUES ($1, $2, $3)
            """
            await self.connection_manager.execute_query(
                create_branch_query,
                [new_branch_id, conversation_id, UUID(message_id)],
            )

            # Add edited message
            add_message_query = """
            INSERT INTO messages (id, conversation_id, parent_id, content, metadata)
            VALUES ($1, $2, $3, $4, $5)
            """
            await self.connection_manager.execute_query(
                add_message_query,
                [
                    new_message_id,
                    conversation_id,
                    parent_id,
                    json.loads(edited_message.json()),
                    {"edited": True},
                ],
            )

            # Link message to new branch
            link_branch_query = """
            INSERT INTO message_branches (message_id, branch_id)
            VALUES ($1, $2)
            """
            await self.connection_manager.execute_query(
                link_branch_query, [new_message_id, new_branch_id]
            )

            # Link ancestors to new branch
            link_ancestors_query = """
            WITH RECURSIVE ancestors AS (
                SELECT parent_id as id
                FROM messages
                WHERE id = $1
                UNION ALL
                SELECT m.parent_id
                FROM messages m
                JOIN ancestors a ON m.id = a.id
                WHERE m.parent_id IS NOT NULL
            )
            INSERT INTO message_branches (message_id, branch_id)
            SELECT id, $2
            FROM ancestors
            WHERE id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
            await self.connection_manager.execute_query(
                link_ancestors_query, [UUID(message_id), new_branch_id]
            )

            # Update descendants' parent
            update_descendants_query = """
            WITH RECURSIVE descendants AS (
                SELECT id
                FROM messages
                WHERE parent_id = $1
                UNION ALL
                SELECT m.id
                FROM messages m
                JOIN descendants d ON m.parent_id = d.id
            )
            UPDATE messages
            SET parent_id = $2
            WHERE id IN (SELECT id FROM descendants)
            """
            await self.connection_manager.execute_query(
                update_descendants_query, [UUID(message_id), new_message_id]
            )

        await self.connection_manager.execute_query(
            "BEGIN", isolation_level="serializable"
        )
        try:
            await transaction()
            await self.connection_manager.execute_query("COMMIT")
        except Exception as e:
            await self.connection_manager.execute_query("ROLLBACK")
            raise e

        return str(new_message_id), str(new_branch_id)

    async def get_next_branch(self, current_branch_id: str) -> Optional[str]:
        """Get the ID of the next branch in chronological order."""
        query = """
        SELECT id FROM branches
        WHERE conversation_id = (
            SELECT conversation_id
            FROM branches
            WHERE id = $1
        )
        AND created_at > (
            SELECT created_at
            FROM branches
            WHERE id = $1
        )
        ORDER BY created_at
        LIMIT 1
        """
        row = await self.connection_manager.fetchrow_query(
            query, [UUID(current_branch_id)]
        )
        return str(row["id"]) if row else None

    async def get_prev_branch(self, current_branch_id: str) -> Optional[str]:
        """Get the ID of the previous branch in chronological order."""
        query = """
        SELECT id FROM branches
        WHERE conversation_id = (
            SELECT conversation_id
            FROM branches
            WHERE id = $1
        )
        AND created_at < (
            SELECT created_at
            FROM branches
            WHERE id = $1
        )
        ORDER BY created_at DESC
        LIMIT 1
        """
        row = await self.connection_manager.fetchrow_query(
            query, [UUID(current_branch_id)]
        )
        return str(row["id"]) if row else None

    async def branch_at_message(self, message_id: str) -> str:
        """Create a new branch starting at a specific message."""
        new_branch_id = UUID(bytes=os.urandom(16))

        async def transaction():
            # Get conversation_id
            get_conv_query = """
            SELECT conversation_id FROM messages WHERE id = $1
            """
            row = await self.connection_manager.fetchrow_query(
                get_conv_query, [UUID(message_id)]
            )

            if not row:
                raise ValueError(f"Message {message_id} not found")

            conversation_id = row["conversation_id"]

            # Check if message is already a branch point
            check_branch_query = """
            SELECT id FROM branches WHERE branch_point_id = $1
            """
            row = await self.connection_manager.fetchrow_query(
                check_branch_query, [UUID(message_id)]
            )

            if row:
                return str(row["id"])

            # Create new branch
            create_branch_query = """
            INSERT INTO branches (id, conversation_id, branch_point_id)
            VALUES ($1, $2, $3)
            """
            await self.connection_manager.execute_query(
                create_branch_query,
                [new_branch_id, conversation_id, UUID(message_id)],
            )

            # Link ancestors to new branch
            link_ancestors_query = """
            WITH RECURSIVE ancestors AS (
                SELECT id FROM messages WHERE id = $1
                UNION ALL
                SELECT m.parent_id
                FROM messages m
                JOIN ancestors a ON m.id = a.id
                WHERE m.parent_id IS NOT NULL
            )
            INSERT INTO message_branches (message_id, branch_id)
            SELECT id, $2
            FROM ancestors
            WHERE id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
            await self.connection_manager.execute_query(
                link_ancestors_query, [UUID(message_id), new_branch_id]
            )

            return str(new_branch_id)

        # Execute transaction
        await self.connection_manager.execute_query(
            "BEGIN", isolation_level="serializable"
        )
        try:
            result = await transaction()
            await self.connection_manager.execute_query("COMMIT")
            return result
        except Exception as e:
            await self.connection_manager.execute_query("ROLLBACK")
            raise e

    async def close(self) -> None:
        """Close the connection to the database."""
        # await self.connection_manager.close()
        pass
