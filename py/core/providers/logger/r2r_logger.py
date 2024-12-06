import csv
import io
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from fastapi.responses import StreamingResponse

from core.base import Message
from core.base.logger.base import (
    PersistentLoggingConfig,
    PersistentLoggingProvider,
    RunInfoLog,
    RunType,
)
from shared.api.models.management.responses import (
    ConversationResponse,
    MessageResponse,
)

logger = logging.getLogger()


class SqlitePersistentLoggingProvider(PersistentLoggingProvider):
    def __init__(self, config: PersistentLoggingConfig):
        self.log_table = config.log_table
        self.log_info_table = config.log_info_table
        # TODO - Should we re-consider this naming convention?
        self.project_name = os.getenv("R2R_PROJECT_NAME", "r2r_default")
        self.logging_path = config.logging_path or os.getenv(
            "LOCAL_DB_PATH", "local.sqlite"
        )
        if not self.logging_path:
            raise ValueError(
                "Please set the environment variable LOCAL_DB_PATH."
            )
        self.conn = None
        try:
            import aiosqlite

            self.aiosqlite = aiosqlite
        except ImportError:
            raise ImportError(
                "Please install aiosqlite to use the SqlitePersistentLoggingProvider."
            )

    async def initialize(self):
        """Initialize the database connection and tables."""
        if self.conn is None:
            self.conn = await self.aiosqlite.connect(self.logging_path)
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.project_name}_{self.log_table} (
                timestamp DATETIME,
                run_id TEXT,
                key TEXT,
                value TEXT
            )
            """
        )
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.project_name}_{self.log_info_table} (
                timestamp DATETIME,
                run_id TEXT UNIQUE,
                run_type TEXT,
                user_id TEXT
            )
        """
        )
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                created_at REAL
                name TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                parent_id TEXT,
                content TEXT,
                created_at REAL,
                metadata TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (parent_id) REFERENCES messages(id)
            );

            CREATE TABLE IF NOT EXISTS branches (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                branch_point_id TEXT,
                created_at REAL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (branch_point_id) REFERENCES messages(id)
            );

            CREATE TABLE IF NOT EXISTS message_branches (
                message_id TEXT,
                branch_id TEXT,
                PRIMARY KEY (message_id, branch_id),
                FOREIGN KEY (message_id) REFERENCES messages(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id)
            );
        """
        )

        async with self.conn.execute(
            "PRAGMA table_info(conversations);"
        ) as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            # Add 'user_id' column if it doesn't exist
            if "user_id" not in column_names:
                await self.conn.execute(
                    "ALTER TABLE conversations ADD COLUMN user_id TEXT;"
                )
            # Add 'name' column if it doesn't exist
            if "name" not in column_names:
                await self.conn.execute(
                    "ALTER TABLE conversations ADD COLUMN name TEXT;"
                )

        await self.conn.commit()

    async def __aenter__(self):
        if self.conn is None:
            await self.initialize()  # Fixed incorrect _init() reference
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    @asynccontextmanager
    async def savepoint(self, name: str):
        """Create a savepoint with proper error handling."""
        if self.conn is None:
            await self.initialize()
        assert self.conn is not None
        async with self.conn.cursor() as cursor:
            await cursor.execute(f"SAVEPOINT {name}")
            try:
                yield
                await cursor.execute(f"RELEASE SAVEPOINT {name}")
            except Exception:
                await cursor.execute(f"ROLLBACK TO SAVEPOINT {name}")
                raise

    async def log(
        self,
        run_id: UUID,
        key: str,
        value: str,
    ):
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        await self.conn.execute(
            f"""
            INSERT INTO {self.project_name}_{self.log_table} (timestamp, run_id, key, value)
            VALUES (datetime('now'), ?, ?, ?)
            """,
            (str(run_id), key, value),
        )
        await self.conn.commit()

    async def info_log(
        self,
        run_id: UUID,
        run_type: RunType,
        user_id: UUID,
    ):
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        await self.conn.execute(
            f"""
            INSERT INTO {self.project_name}_{self.log_info_table} (timestamp, run_id, run_type, user_id)
            VALUES (datetime('now'), ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
            timestamp = datetime('now'),
            run_type = excluded.run_type,
            user_id = excluded.user_id
            """,
            (str(run_id), str(run_type), str(user_id)),
        )
        await self.conn.commit()

    async def get_info_logs(
        self,
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        cursor = await self.conn.cursor()
        query = "SELECT run_id, run_type, timestamp, user_id"
        query += f" FROM {self.project_name}_{self.log_info_table}"
        conditions = []
        params = []
        if run_type_filter:
            conditions.append("run_type = ?")
            params.append(str(run_type_filter))
        if user_ids:
            conditions.append(f"user_id IN ({','.join(['?']*len(user_ids))})")
            params.extend([str(user_id) for user_id in user_ids])
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        return [
            RunInfoLog(
                run_id=UUID(row[0]),
                run_type=row[1],
                timestamp=datetime.fromisoformat(row[2]),
                user_id=UUID(row[3]),
            )
            for row in rows
        ]

    async def create_conversation(
        self,
        user_id: Optional[UUID] = None,
        name: Optional[str] = None,
    ) -> ConversationResponse:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        conversation_id = str(uuid.uuid4())
        created_at = datetime.utcnow().timestamp()

        await self.conn.execute(
            """
            INSERT INTO conversations (id, user_id, created_at, name)
            VALUES (?, ?, ?, ?)
            """,
            (
                conversation_id,
                str(user_id) if user_id else None,
                created_at,
                name,
            ),
        )
        await self.conn.commit()
        return ConversationResponse(
            id=conversation_id,
            created_at=created_at,
        )

    async def verify_conversation_access(
        self, conversation_id: UUID, user_id: UUID
    ) -> bool:

        if not self.conn:
            raise ValueError("Connection pool not initialized.")

        async with self.conn.execute(
            """
            SELECT 1 FROM conversations
            WHERE id = ? AND (user_id IS NULL OR user_id = ?)
            """,
            (str(conversation_id), str(user_id)),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_conversations_overview(
        self,
        offset: int,
        limit: int,
        user_ids: Optional[UUID | list[UUID]] = None,
        conversation_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[dict] | int]:
        """
        Get conversations overview with pagination.
        If user_ids is None, returns all conversations (superuser access)
        If user_ids is a single UUID, returns conversations for that user
        If user_ids is a list of UUIDs, returns conversations for those users
        """
        query = """
            WITH conversation_overview AS (
                SELECT c.id, c.created_at, c.user_id, c.name
                FROM conversations c
                WHERE 1=1
                {user_where_clause}
                {conversation_where_clause}
            ),
            counted_overview AS (
                SELECT *, COUNT(*) OVER() AS total_entries
                FROM conversation_overview
            )
            SELECT * FROM counted_overview
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """

        params = []

        if user_ids is None:
            user_where_clause = ""
        elif isinstance(user_ids, UUID):
            user_where_clause = "AND c.user_id = ?"
            params.append(str(user_ids))
        else:
            user_where_clause = (
                f"AND c.user_id IN ({','.join(['?' for _ in user_ids])})"
            )
            params.extend(str(uid) for uid in user_ids)

        if conversation_ids:
            conversation_where_clause = (
                f"AND c.id IN ({','.join(['?' for _ in conversation_ids])})"
            )
            params.extend(str(cid) for cid in conversation_ids)
        else:
            conversation_where_clause = ""

        params.extend([str(limit) if limit != -1 else "-1", str(offset)])

        query = query.format(
            user_where_clause=user_where_clause,
            conversation_where_clause=conversation_where_clause,
        )

        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to query."
            )

        async with self.conn.execute(query, params) as cursor:
            results = await cursor.fetchall()

        if not results:
            return {"results": [], "total_entries": 0}

        conversations = [
            {
                "id": row[0],
                "created_at": row[1],
                "user_id": UUID(row[2]) if row[2] else None,
                "name": row[3] or None,
            }
            for row in results
        ]

        total_entries = results[0][-1] if results else 0

        return {"results": conversations, "total_entries": total_entries}

    async def add_message(
        self,
        conversation_id: UUID,
        content: Message,
        parent_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
    ) -> MessageResponse:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        message_id = str(uuid.uuid4())
        created_at = datetime.utcnow().timestamp()

        content_json = content.model_dump_json()

        await self.conn.execute(
            "INSERT INTO messages (id, conversation_id, parent_id, content, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (
                message_id,
                str(conversation_id),
                str(parent_id),
                content_json,
                created_at,
                json.dumps(metadata or {}),
            ),
        )

        if parent_id is not None:
            await self.conn.execute(
                """
                INSERT INTO message_branches (message_id, branch_id)
                SELECT ?, branch_id FROM message_branches WHERE message_id = ?
                """,
                (message_id, str(parent_id)),
            )
        else:
            # For messages with no parent, use the most recent branch, or create a new one
            async with self.conn.execute(
                """
                SELECT id FROM branches
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (str(conversation_id),),
            ) as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    branch_id = row[0]
                else:
                    # Create a new branch if none exists
                    branch_id = str(uuid.uuid4())
                    await self.conn.execute(
                        """
                        INSERT INTO branches (id, conversation_id, branch_point_id, created_at) VALUES (?, ?, NULL, ?)
                        """,
                        (branch_id, str(conversation_id), created_at),
                    )
                await self.conn.execute(
                    """
                    INSERT INTO message_branches (message_id, branch_id) VALUES (?, ?)
                    """,
                    (message_id, branch_id),
                )

        await self.conn.commit()
        return MessageResponse(
            id=message_id,
            message=content,
        )

    async def edit_message(
        self, message_id: UUID, new_content: str
    ) -> Tuple[str, str]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        # Get the original message details
        async with self.conn.execute(
            "SELECT conversation_id, parent_id, content FROM messages WHERE id = ?",
            (str(message_id),),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(f"Message {message_id} not found")
            conversation_id, parent_id, old_content_json = row
            # Parse the old content to get the original Message object
            old_message = Message.parse_raw(old_content_json)

        # Create a new Message object with the updated content
        edited_message = Message(
            role=old_message.role,
            content=new_content,
            name=old_message.name,
            function_call=old_message.function_call,
            tool_calls=old_message.tool_calls,
        )

        # Create a new branch
        new_branch_id = str(uuid.uuid4())
        created_at = datetime.utcnow().timestamp()
        await self.conn.execute(
            "INSERT INTO branches (id, conversation_id, branch_point_id, created_at) VALUES (?, ?, ?, ?)",
            (new_branch_id, conversation_id, str(message_id), created_at),
        )

        # Add the edited message with the same parent_id
        new_message_id = str(uuid.uuid4())
        message_created_at = datetime.utcnow().timestamp()

        edited_message_json = edited_message.model_dump_json()

        await self.conn.execute(
            "INSERT INTO messages (id, conversation_id, parent_id, content, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (
                new_message_id,
                conversation_id,
                parent_id,
                edited_message_json,  # Use the serialized JSON string
                message_created_at,
                json.dumps({"edited": True}),
            ),
        )
        # Link the new message to the new branch
        await self.conn.execute(
            "INSERT INTO message_branches (message_id, branch_id) VALUES (?, ?)",
            (new_message_id, new_branch_id),
        )

        # Link ancestor messages (excluding the original message) to the new branch
        await self.conn.execute(
            """
            WITH RECURSIVE ancestors(id) AS (
                SELECT parent_id FROM messages WHERE id = ?
                UNION ALL
                SELECT m.parent_id FROM messages m JOIN ancestors a ON m.id = a.id WHERE m.parent_id IS NOT NULL
            )
            INSERT OR IGNORE INTO message_branches (message_id, branch_id)
            SELECT id, ? FROM ancestors WHERE id IS NOT NULL
        """,
            (message_id, new_branch_id),
        )

        # Update the parent_id of the edited message's descendants in the new branch
        await self.conn.execute(
            """
            WITH RECURSIVE descendants(id) AS (
                SELECT id FROM messages WHERE parent_id = ?
                UNION ALL
                SELECT m.id FROM messages m JOIN descendants d ON m.parent_id = d.id
            )
            UPDATE messages
            SET parent_id = ?
            WHERE id IN (SELECT id FROM descendants)
        """,
            (message_id, new_message_id),
        )

        await self.conn.commit()
        return new_message_id, new_branch_id

    async def update_message_metadata(
        self, message_id: UUID, metadata: dict
    ) -> None:
        """Update metadata for a specific message."""

        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        try:
            await self.conn.execute("BEGIN TRANSACTION")

            cursor = await self.conn.execute(
                "SELECT metadata FROM messages WHERE id = ?",
                (str(message_id),),
            )
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"Message {message_id} not found")
            current_metadata_json = row[0]
            current_metadata = (
                json.loads(current_metadata_json)
                if current_metadata_json
                else {}
            )

            updated_metadata = {**current_metadata, **metadata}
            updated_metadata_json = json.dumps(updated_metadata)

            await self.conn.execute(
                "UPDATE messages SET metadata = ? WHERE id = ?",
                (updated_metadata_json, str(message_id)),
            )

            await self.conn.commit()

        except Exception as e:
            await self.conn.rollback()
            raise e

    async def export_messages_to_csv(
        self, chunk_size: int = 1000, return_type: str = "stream"
    ) -> StreamingResponse | str:
        """
        Export messages table to CSV format.

        Args:
            chunk_size: Number of records to process at once
            return_type: Either "stream" or "string"

        Returns:
            StreamingResponse or string depending on return_type
        """
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async def generate_csv():
            buffer = io.StringIO()
            writer = csv.writer(buffer)

            # Write headers
            async with self.conn.execute(
                "SELECT * FROM messages LIMIT 1"
            ) as cursor:
                column_names = [
                    description[0] for description in cursor.description
                ]
                writer.writerow(column_names)
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()

            # Stream rows in chunks
            offset = 0
            while True:
                async with self.conn.execute(
                    "SELECT * FROM messages LIMIT ? OFFSET ?",
                    (chunk_size, offset),
                ) as cursor:
                    rows = await cursor.fetchall()
                    if not rows:
                        break

                    for row in rows:
                        writer.writerow(row)
                    chunk_data = buffer.getvalue()
                    yield chunk_data
                    buffer.seek(0)
                    buffer.truncate()

                offset += chunk_size

        if return_type == "stream":
            return StreamingResponse(
                generate_csv(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=messages.csv"
                },
            )
        else:
            # For string return, accumulate all data
            csv_data = io.StringIO()
            writer = csv.writer(csv_data)

            async with self.conn.execute(
                "SELECT * FROM messages LIMIT 1"
            ) as cursor:
                column_names = [
                    description[0] for description in cursor.description
                ]
                writer.writerow(column_names)

            async with self.conn.execute("SELECT * FROM messages") as cursor:
                rows = await cursor.fetchall()
                writer.writerows(rows)

            return csv_data.getvalue()

    async def get_conversation(
        self,
        conversation_id: UUID,
        branch_id: Optional[UUID] = None,
    ) -> list[MessageResponse]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        # Debug: Check if messages exist for this conversation
        async with self.conn.execute(
            "SELECT id, content, parent_id FROM messages WHERE conversation_id = ?",
            (str(conversation_id),),
        ) as cursor:
            messages = await cursor.fetchall()

        if branch_id is None:
            # Debug: Check branches query
            async with self.conn.execute(
                """
                SELECT id FROM branches
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (str(conversation_id),),
            ) as cursor:
                row = await cursor.fetchone()
                branch_id = row[0] if row else None

        if branch_id:
            # Debug: Check message_branches entries
            async with self.conn.execute(
                """
                SELECT message_id, branch_id
                FROM message_branches
                WHERE branch_id = ?
                """,
                (str(branch_id),),
            ) as cursor:
                message_branches = await cursor.fetchall()

        # Get conversation details first
        async with self.conn.execute(
            "SELECT created_at FROM conversations WHERE id = ?",
            (str(conversation_id),),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(
                    Message=f"Conversation {conversation_id} not found"
                )
            conversation_created_at = row[0]

        if branch_id is None:
            # Get the most recent branch by created_at timestamp
            async with self.conn.execute(
                """
                SELECT id FROM branches
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (str(conversation_id),),
            ) as cursor:
                row = await cursor.fetchone()
                print(f"Row: {row}")
                branch_id = row[0] if row else None

        # If no branch exists, return empty results but with required fields
        if branch_id is None:
            logger.warning(
                f"No branches found for conversation ID {conversation_id}"
            )
            return None

        # Get all messages for this branch
        async with self.conn.execute(
            """
            WITH RECURSIVE branch_messages(id, content, parent_id, depth, created_at, metadata) AS (
                SELECT m.id, m.content, m.parent_id, 0, m.created_at, m.metadata
                FROM messages m
                JOIN message_branches mb ON m.id = mb.message_id
                WHERE mb.branch_id = ? AND (m.parent_id IS NULL OR m.parent_id = 'None')
                UNION
                SELECT m.id, m.content, m.parent_id, bm.depth + 1, m.created_at, m.metadata
                FROM messages m
                JOIN message_branches mb ON m.id = mb.message_id
                JOIN branch_messages bm ON m.parent_id = bm.id
                WHERE mb.branch_id = ?
            )
            SELECT id, content, parent_id, metadata FROM branch_messages
            ORDER BY created_at ASC
            """,
            (str(branch_id), str(branch_id)),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                MessageResponse(
                    id=row[0],
                    message=Message.parse_raw(row[1]),
                    metadata=json.loads(row[3]) if row[3] else {},
                )
                for row in rows
            ]

    async def get_branches(
        self,
        offset: int,
        limit: int,
        conversation_id: UUID,
    ) -> dict:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        query = """
            WITH branch_data AS (
                SELECT b.id, b.branch_point_id, m.content, b.created_at
                FROM branches b
                LEFT JOIN messages m ON b.branch_point_id = m.id
                WHERE b.conversation_id = ?
            ),
            counted_branches AS (
                SELECT *, COUNT(*) OVER() as total_entries
                FROM branch_data
            )
            SELECT * FROM counted_branches
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """

        async with self.conn.execute(
            query, (str(conversation_id), limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            return {"results": [], "total_entries": 0}

        branches = [
            {
                "branch_id": row[0],
                "branch_point_id": row[1],
                "content": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

        total_entries = rows[0][-1] if rows else 0

        return {"results": branches, "total_entries": total_entries}

    async def get_next_branch(self, current_branch_id: UUID) -> Optional[str]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.conn.execute(
            """
            SELECT id FROM branches
            WHERE conversation_id = (SELECT conversation_id FROM branches WHERE id = ?)
            AND created_at > (SELECT created_at FROM branches WHERE id = ?)
            ORDER BY created_at
            LIMIT 1
        """,
            (str(current_branch_id), str(current_branch_id)),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_prev_branch(self, current_branch_id: UUID) -> Optional[str]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.conn.execute(
            """
            SELECT id FROM branches
            WHERE conversation_id = (SELECT conversation_id FROM branches WHERE id = ?)
            AND created_at < (SELECT created_at FROM branches WHERE id = ?)
            ORDER BY created_at DESC
            LIMIT 1
        """,
            (str(current_branch_id), str(current_branch_id)),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def branch_at_message(self, message_id: UUID) -> str:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        # Get the conversation_id of the message
        async with self.conn.execute(
            "SELECT conversation_id FROM messages WHERE id = ?",
            (str(message_id),),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(f"Message {message_id} not found")
            conversation_id = row[0]

        # Check if the message is already a branch point
        async with self.conn.execute(
            "SELECT id FROM branches WHERE branch_point_id = ?",
            (str(message_id),),
        ) as cursor:
            row = await cursor.fetchone()
            if row is not None:
                return row[0]  # Return the existing branch ID

        # Create a new branch starting from message_id
        new_branch_id = str(uuid.uuid4())
        created_at = datetime.utcnow().timestamp()
        await self.conn.execute(
            "INSERT INTO branches (id, conversation_id, branch_point_id, created_at) VALUES (?, ?, ?, ?)",
            (new_branch_id, conversation_id, str(message_id), created_at),
        )

        # Link ancestor messages to the new branch
        await self.conn.execute(
            """
            WITH RECURSIVE ancestors(id) AS (
                SELECT id FROM messages WHERE id = ?
                UNION ALL
                SELECT m.parent_id FROM messages m JOIN ancestors a ON m.id = a.id WHERE m.parent_id IS NOT NULL
            )
            INSERT OR IGNORE INTO message_branches (message_id, branch_id)
            SELECT id, ? FROM ancestors
        """,
            (str(message_id), new_branch_id),
        )

        await self.conn.commit()
        return new_branch_id

    async def delete_conversation(self, conversation_id: UUID):
        """Delete a conversation and all related data."""
        if self.conn is None:
            await self.initialize()
        try:
            assert self.conn is not None
            # Delete all message branches associated with the conversation
            await self.conn.execute(
                "DELETE FROM message_branches WHERE message_id IN (SELECT id FROM messages WHERE conversation_id = ?)",
                (str(conversation_id),),
            )
            # Delete all branches associated with the conversation
            await self.conn.execute(
                "DELETE FROM branches WHERE conversation_id = ?",
                (str(conversation_id),),
            )
            # Delete all messages associated with the conversation
            await self.conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (str(conversation_id),),
            )
            # Finally, delete the conversation itself
            await self.conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (str(conversation_id),),
            )
            await self.conn.commit()
        except Exception:
            assert self.conn is not None
            await self.conn.rollback()
            raise

    async def get_logs(
        self,
        run_ids: list[UUID],
        limit_per_run: int = 10,
    ) -> list:
        if not run_ids:
            raise ValueError("No run ids provided.")
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        cursor = await self.conn.cursor()
        placeholders = ",".join(["?" for _ in run_ids])
        query = f"""
        SELECT run_id, key, value, timestamp
        FROM {self.project_name}_{self.log_table}
        WHERE run_id IN ({placeholders})
        ORDER BY timestamp DESC
        """

        params = [str(run_id) for run_id in run_ids]

        await cursor.execute(query, params)
        rows = await cursor.fetchall()

        # Post-process the results to limit per run_id and ensure only requested run_ids are included
        result = []
        run_id_count = {str(run_id): 0 for run_id in run_ids}
        for row in rows:
            row_dict = dict(zip([d[0] for d in cursor.description], row))
            row_run_id = row_dict["run_id"]
            if (
                row_run_id in run_id_count
                and run_id_count[row_run_id] < limit_per_run
            ):
                row_dict["run_id"] = UUID(row_dict["run_id"])
                result.append(row_dict)
                run_id_count[row_run_id] += 1
        return result
