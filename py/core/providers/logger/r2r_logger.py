import logging
import json
import os
import uuid
from datetime import datetime
from typing import Optional, Tuple, Union
from uuid import UUID

from core.base import Message
from core.base.logger.base import RunType
from core.base.logger.base import (
    PersistentLoggingConfig,
    PersistentLoggingProvider,
    RunInfoLog,
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
                created_at REAL
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
        await self.conn.commit()

    async def __aenter__(self):
        if self.conn is None:
            await self._init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

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
            (str(run_id), run_type, str(user_id)),
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
            params.append(run_type_filter)
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

    async def create_conversation(self) -> str:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        conversation_id = str(uuid.uuid4())
        created_at = datetime.utcnow().timestamp()

        await self.conn.execute(
            "INSERT INTO conversations (id, created_at) VALUES (?, ?)",
            (conversation_id, created_at),
        )
        await self.conn.commit()
        return conversation_id

    async def get_conversations_overview(
        self,
        conversation_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = -1,
    ) -> dict[str, Union[list[dict], int]]:
        """Get an overview of conversations, optionally filtered by conversation IDs, with pagination."""
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
            LIMIT ? OFFSET ?
        """

        where_clause = (
            f"WHERE c.id IN ({','.join(['?' for _ in conversation_ids])})"
            if conversation_ids
            else ""
        )
        query = query.format(where_clause=where_clause)

        params: list = []
        if conversation_ids:
            params.extend(conversation_ids)
        params.extend((limit if limit != -1 else -1, offset))

        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.conn.execute(query, params) as cursor:
            results = await cursor.fetchall()

        if not results:
            logger.info("No conversations found.")
            return {"results": [], "total_entries": 0}

        conversations = [
            {
                "conversation_id": row[0],
                "created_at": row[1],
            }
            for row in results
        ]

        total_entries = results[0][-1] if results else 0

        return {"results": conversations, "total_entries": total_entries}

    async def add_message(
        self,
        conversation_id: str,
        content: Message,
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        message_id = str(uuid.uuid4())
        created_at = datetime.utcnow().timestamp()

        await self.conn.execute(
            "INSERT INTO messages (id, conversation_id, parent_id, content, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (
                message_id,
                conversation_id,
                parent_id,
                content.json(),
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
                (message_id, parent_id),
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
                (conversation_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is not None:
                    branch_id = row[0]
                else:
                    # Create a new branch if none exists
                    branch_id = str(uuid.uuid4())
                    await self.conn.execute(
                        """
                        INSERT INTO branches (id, conversation_id, branch_point_id) VALUES (?, ?, NULL)
                        """,
                        (branch_id, conversation_id),
                    )
                await self.conn.execute(
                    """
                    INSERT INTO message_branches (message_id, branch_id) VALUES (?, ?)
                    """,
                    (message_id, branch_id),
                )

        await self.conn.commit()
        return message_id

    async def edit_message(
        self, message_id: str, new_content: str
    ) -> Tuple[str, str]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        # Get the original message details
        async with self.conn.execute(
            "SELECT conversation_id, parent_id, content FROM messages WHERE id = ?",
            (message_id,),
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
            (new_branch_id, conversation_id, message_id, created_at),
        )

        # Add the edited message with the same parent_id
        new_message_id = str(uuid.uuid4())
        message_created_at = datetime.utcnow().timestamp()
        await self.conn.execute(
            "INSERT INTO messages (id, conversation_id, parent_id, content, created_at, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (
                new_message_id,
                conversation_id,
                parent_id,
                edited_message.json(),
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

    async def get_conversation(
        self, conversation_id: str, branch_id: Optional[str] = None
    ) -> Tuple[str, list[Message]]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        if branch_id is None:
            # Get the most recent branch by created_at timestamp
            async with self.conn.execute(
                """
                SELECT id FROM branches
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (conversation_id,),
            ) as cursor:
                row = await cursor.fetchone()
                branch_id = row[0] if row else None

        if branch_id is None:
            return []  # No branches found for the conversation

        # Get all messages for this branch
        async with self.conn.execute(
            """
            WITH RECURSIVE branch_messages(id, content, parent_id, depth, created_at) AS (
                SELECT m.id, m.content, m.parent_id, 0, m.created_at
                FROM messages m
                JOIN message_branches mb ON m.id = mb.message_id
                WHERE mb.branch_id = ? AND m.parent_id IS NULL
                UNION
                SELECT m.id, m.content, m.parent_id, bm.depth + 1, m.created_at
                FROM messages m
                JOIN message_branches mb ON m.id = mb.message_id
                JOIN branch_messages bm ON m.parent_id = bm.id
                WHERE mb.branch_id = ?
            )
            SELECT id, content, parent_id FROM branch_messages
            ORDER BY created_at ASC
        """,
            (branch_id, branch_id),
        ) as cursor:
            rows = await cursor.fetchall()
            return [(row[0], Message.parse_raw(row[1])) for row in rows]

    async def get_branches_overview(self, conversation_id: str) -> list[dict]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.conn.execute(
            """
            SELECT b.id, b.branch_point_id, m.content, b.created_at
            FROM branches b
            LEFT JOIN messages m ON b.branch_point_id = m.id
            WHERE b.conversation_id = ?
            ORDER BY b.created_at
        """,
            (conversation_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "branch_id": row[0],
                    "branch_point_id": row[1],
                    "content": row[2],
                    "created_at": row[3],
                }
                for row in rows
            ]

    async def get_next_branch(self, current_branch_id: str) -> Optional[str]:
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
            (current_branch_id, current_branch_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_prev_branch(self, current_branch_id: str) -> Optional[str]:
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
            (current_branch_id, current_branch_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def branch_at_message(self, message_id: str) -> str:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        # Get the conversation_id of the message
        async with self.conn.execute(
            "SELECT conversation_id FROM messages WHERE id = ?",
            (message_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(f"Message {message_id} not found")
            conversation_id = row[0]

        # Check if the message is already a branch point
        async with self.conn.execute(
            "SELECT id FROM branches WHERE branch_point_id = ?",
            (message_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is not None:
                return row[0]  # Return the existing branch ID

        # Create a new branch starting from message_id
        new_branch_id = str(uuid.uuid4())
        await self.conn.execute(
            "INSERT INTO branches (id, conversation_id, branch_point_id) VALUES (?, ?, ?)",
            (new_branch_id, conversation_id, message_id),
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
            (message_id, new_branch_id),
        )

        await self.conn.commit()
        return new_branch_id

    async def delete_conversation(self, conversation_id: str):
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        # Begin a transaction
        async with self.conn.execute("BEGIN TRANSACTION"):
            # Delete all message branches associated with the conversation
            await self.conn.execute(
                "DELETE FROM message_branches WHERE message_id IN (SELECT id FROM messages WHERE conversation_id = ?)",
                (conversation_id,),
            )
            # Delete all branches associated with the conversation
            await self.conn.execute(
                "DELETE FROM branches WHERE conversation_id = ?",
                (conversation_id,),
            )
            # Delete all messages associated with the conversation
            await self.conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            # Finally, delete the conversation itself
            await self.conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
            # Commit the transaction
            await self.conn.commit()

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


class PostgresPersistentLoggingProvider(PersistentLoggingProvider):
    def __init__(self, config: PersistentLoggingConfig):
        self.log_table = config.log_table
        self.log_info_table = config.log_info_table
        self.project_name = os.getenv("R2R_PROJECT_NAME", "r2r_default")

        # PostgreSQL connection settings
        self.db_host = os.getenv("R2R_POSTGRES_HOST", "localhost")
        self.db_port = os.getenv("R2R_POSTGRES_PORT", "5432")
        self.db_name = os.getenv("R2R_POSTGRES_DB")
        self.db_user = os.getenv("R2R_POSTGRES_USER")
        self.db_password = os.getenv("R2R_POSTGRES_PASSWORD")

        if not all([self.db_name, self.db_user, self.db_password]):
            raise ValueError(
                "Please set all required PostgreSQL environment variables: "
                "POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD"
            )

        self.conn = None
        try:
            import asyncpg

            self.asyncpg = asyncpg
        except ImportError:
            raise ImportError(
                "Please install asyncpg to use the PostgresPersistentLoggingProvider."
            )

    async def initialize(self):
        self.conn = await self.asyncpg.connect(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.db_user,
            password=self.db_password,
        )

        # Create schema if it doesn't exist
        await self.conn.execute(
            f"CREATE SCHEMA IF NOT EXISTS {self.project_name}"
        )

        # Create log tables
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.project_name}.{self.log_table} (
                timestamp TIMESTAMP WITH TIME ZONE,
                run_id UUID,
                key TEXT,
                value TEXT
            )
        """
        )

        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.project_name}.{self.log_info_table} (
                timestamp TIMESTAMP WITH TIME ZONE,
                run_id UUID UNIQUE,
                run_type TEXT,
                user_id UUID
            )
        """
        )

        # Create conversation-related tables
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id UUID PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE
            );

            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY,
                conversation_id UUID REFERENCES conversations(id),
                parent_id UUID REFERENCES messages(id),
                content JSONB,
                created_at TIMESTAMP WITH TIME ZONE,
                metadata JSONB
            );

            CREATE TABLE IF NOT EXISTS branches (
                id UUID PRIMARY KEY,
                conversation_id UUID REFERENCES conversations(id),
                branch_point_id UUID REFERENCES messages(id),
                created_at TIMESTAMP WITH TIME ZONE
            );

            CREATE TABLE IF NOT EXISTS message_branches (
                message_id UUID REFERENCES messages(id),
                branch_id UUID REFERENCES branches(id),
                PRIMARY KEY (message_id, branch_id)
            );
        """
        )

    async def __aenter__(self):
        if self.conn is None:
            await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

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
            INSERT INTO {self.project_name}.{self.log_table}
            (timestamp, run_id, key, value)
            VALUES (CURRENT_TIMESTAMP, $1, $2, $3)
            """,
            run_id,
            key,
            value,
        )

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
            INSERT INTO {self.project_name}.{self.log_info_table}
            (timestamp, run_id, run_type, user_id)
            VALUES (CURRENT_TIMESTAMP, $1, $2, $3)
            ON CONFLICT (run_id) DO UPDATE SET
                timestamp = CURRENT_TIMESTAMP,
                run_type = EXCLUDED.run_type,
                user_id = EXCLUDED.user_id
            """,
            run_id,
            run_type,
            user_id,
        )

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

        query = f"""
            SELECT run_id, run_type, timestamp, user_id
            FROM {self.project_name}.{self.log_info_table}
            WHERE 1=1
        """
        params = []
        if run_type_filter:
            query += " AND run_type = $1"
            params.append(run_type_filter)
        if user_ids:
            query += f" AND user_id = ANY(${len(params) + 1})"
            params.append(user_ids)

        query += " ORDER BY timestamp DESC LIMIT $" + str(len(params) + 1)
        query += " OFFSET $" + str(len(params) + 2)
        params.extend([limit, offset])

        rows = await self.conn.fetch(query, *params)
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
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        conversation_id = uuid.uuid4()
        await self.conn.execute(
            """
            INSERT INTO conversations (id, created_at)
            VALUES ($1, CURRENT_TIMESTAMP)
            """,
            conversation_id,
        )
        return str(conversation_id)

    async def get_conversations_overview(
        self,
        conversation_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = -1,
    ) -> dict[str, Union[list[dict], int]]:
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
        if conversation_ids:
            params.append(conversation_ids)  # type: ignore

        rows = await self.conn.fetch(query, *params)  # type: ignore
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
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        message_id = uuid.uuid4()
        async with self.conn.transaction():
            # Insert message
            await self.conn.execute(
                """
                INSERT INTO messages (id, conversation_id, parent_id, content, created_at, metadata)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, $5)
                """,
                message_id,
                UUID(conversation_id),
                UUID(parent_id) if parent_id else None,
                json.loads(content.json()),
                metadata or {},
            )

            if parent_id:
                # Copy branch associations from parent
                await self.conn.execute(
                    """
                    INSERT INTO message_branches (message_id, branch_id)
                    SELECT $1, branch_id FROM message_branches WHERE message_id = $2
                    """,
                    message_id,
                    UUID(parent_id),
                )
            else:
                # Get or create default branch
                branch_row = await self.conn.fetchrow(
                    """
                    SELECT id FROM branches
                    WHERE conversation_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    UUID(conversation_id),
                )

                branch_id = branch_row["id"] if branch_row else uuid.uuid4()
                if not branch_row:
                    await self.conn.execute(
                        """
                        INSERT INTO branches (id, conversation_id, branch_point_id)
                        VALUES ($1, $2, NULL)
                        """,
                        branch_id,
                        UUID(conversation_id),
                    )

                await self.conn.execute(
                    """
                    INSERT INTO message_branches (message_id, branch_id)
                    VALUES ($1, $2)
                    """,
                    message_id,
                    branch_id,
                )

        return str(message_id)

    async def edit_message(
        self, message_id: str, new_content: str
    ) -> Tuple[str, str]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.conn.transaction():
            # Get original message details
            row = await self.conn.fetchrow(
                """
                SELECT conversation_id, parent_id, content
                FROM messages WHERE id = $1
                """,
                UUID(message_id),
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
            new_branch_id = uuid.uuid4()
            new_message_id = uuid.uuid4()

            await self.conn.execute(
                """
                INSERT INTO branches (id, conversation_id, branch_point_id, created_at)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                """,
                new_branch_id,
                conversation_id,
                UUID(message_id),
            )

            # Add edited message
            await self.conn.execute(
                """
                INSERT INTO messages (id, conversation_id, parent_id, content, created_at, metadata)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, $5)
                """,
                new_message_id,
                conversation_id,
                parent_id,
                json.loads(edited_message.json()),
                {"edited": True},
            )

            # Link message to new branch
            await self.conn.execute(
                """
                INSERT INTO message_branches (message_id, branch_id)
                VALUES ($1, $2)
                """,
                new_message_id,
                new_branch_id,
            )

            # Link ancestors to new branch
            await self.conn.execute(
                """
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
                """,
                UUID(message_id),
                new_branch_id,
            )

            # Update descendants' parent
            await self.conn.execute(
                """
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
                """,
                UUID(message_id),
                new_message_id,
            )

        return str(new_message_id), str(new_branch_id)

    async def get_conversation(
        self, conversation_id: str, branch_id: Optional[str] = None
    ) -> list[tuple[str, Message]]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        if branch_id is None:
            row = await self.conn.fetchrow(
                """
                SELECT id FROM branches
                WHERE conversation_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                UUID(conversation_id),
            )
            branch_id = str(row["id"]) if row else None

        if branch_id is None:
            return []

        rows = await self.conn.fetch(
            """
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
            """,
            UUID(branch_id),
        )
        return [
            (str(row["id"]), Message.parse_raw(json.dumps(row["content"])))
            for row in rows
        ]

    async def get_branches_overview(self, conversation_id: str) -> list[dict]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        rows = await self.conn.fetch(
            """
            SELECT b.id, b.branch_point_id, m.content, b.created_at
            FROM branches b
            LEFT JOIN messages m ON b.branch_point_id = m.id
            WHERE b.conversation_id = $1
            ORDER BY b.created_at
            """,
            UUID(conversation_id),
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

    async def get_next_branch(self, current_branch_id: str) -> Optional[str]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        row = await self.conn.fetchrow(
            """
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
            """,
            UUID(current_branch_id),
        )
        return str(row["id"]) if row else None

    async def get_prev_branch(self, current_branch_id: str) -> Optional[str]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        row = await self.conn.fetchrow(
            """
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
            """,
            UUID(current_branch_id),
        )
        return str(row["id"]) if row else None

    async def branch_at_message(self, message_id: str) -> str:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.conn.transaction():
            # Get conversation_id
            row = await self.conn.fetchrow(
                "SELECT conversation_id FROM messages WHERE id = $1",
                UUID(message_id),
            )
            if not row:
                raise ValueError(f"Message {message_id} not found")
            conversation_id = row["conversation_id"]

            # Check if message is already a branch point
            row = await self.conn.fetchrow(
                "SELECT id FROM branches WHERE branch_point_id = $1",
                UUID(message_id),
            )
            if row:
                return str(row["id"])

            # Create new branch
            new_branch_id = uuid.uuid4()
            await self.conn.execute(
                """
                INSERT INTO branches (id, conversation_id, branch_point_id)
                VALUES ($1, $2, $3)
                """,
                new_branch_id,
                conversation_id,
                UUID(message_id),
            )

            # Link ancestors to new branch
            await self.conn.execute(
                """
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
                """,
                UUID(message_id),
                new_branch_id,
            )

            return str(new_branch_id)

    async def delete_conversation(self, conversation_id: str):
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.conn.transaction():
            # Delete in correct order to respect foreign key constraints
            await self.conn.execute(
                "DELETE FROM message_branches WHERE message_id IN (SELECT id FROM messages WHERE conversation_id = $1)",
                UUID(conversation_id),
            )
            await self.conn.execute(
                "DELETE FROM branches WHERE conversation_id = $1",
                UUID(conversation_id),
            )
            await self.conn.execute(
                "DELETE FROM messages WHERE conversation_id = $1",
                UUID(conversation_id),
            )
            await self.conn.execute(
                "DELETE FROM conversations WHERE id = $1",
                UUID(conversation_id),
            )

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

        rows = await self.conn.fetch(
            f"""
            WITH ranked_logs AS (
                SELECT
                    run_id,
                    key,
                    value,
                    timestamp,
                    ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY timestamp DESC) as rn
                FROM {self.project_name}.{self.log_table}
                WHERE run_id = ANY($1)
            )
            SELECT run_id, key, value, timestamp
            FROM ranked_logs
            WHERE rn <= $2
            ORDER BY timestamp DESC
            """,
            run_ids,
            limit_per_run,
        )

        return [
            {
                "run_id": row["run_id"],
                "key": row["key"],
                "value": row["value"],
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]
