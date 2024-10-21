import json
import logging
import os
import uuid
from abc import abstractmethod
from datetime import datetime
from typing import Any, Optional, Tuple, Union
from uuid import UUID

from pydantic import BaseModel

from core.base import Message

from ..providers.base import Provider, ProviderConfig
from .base import RunType

logger = logging.getLogger()


class RunInfoLog(BaseModel):
    run_id: UUID
    run_type: str
    timestamp: datetime
    user_id: UUID


class LoggingConfig(ProviderConfig):
    provider: str = "local"
    log_table: str = "logs"
    log_info_table: str = "log_info"
    logging_path: Optional[str] = None

    def validate_config(self) -> None:
        pass

    @property
    def supported_providers(self) -> list[str]:
        return ["local", "postgres"]


class RunLoggingProvider(Provider):
    @abstractmethod
    async def close(self):
        pass

    @abstractmethod
    async def log(
        self,
        run_id: UUID,
        key: str,
        value: str,
    ):
        pass

    @abstractmethod
    async def get_logs(
        self,
        run_ids: list[UUID],
        limit_per_run: int,
    ) -> list:
        pass

    @abstractmethod
    async def info_log(
        self,
        run_id: UUID,
        run_type: RunType,
        user_id: UUID,
    ):
        pass

    @abstractmethod
    async def get_info_logs(
        self,
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        pass


class SqlitePersistentLoggingProvider(RunLoggingProvider):
    def __init__(self, config: LoggingConfig):
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

    async def _init(self):
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


class HatchetLogger:
    def __init__(self, context: Any):
        self.context = context

    def _log(self, level: str, message: str, function: Optional[str] = None):
        if function:
            log_message = f"[{level}]: {function}: {message}"
        else:
            log_message = f"[{level}]: {message}"
        self.context.log(log_message)

    def debug(self, message: str, function: Optional[str] = None):
        self._log("DEBUG", message, function)

    def info(self, message: str, function: Optional[str] = None):
        self._log("INFO", message, function)

    def warning(self, message: str, function: Optional[str] = None):
        self._log("WARNING", message, function)

    def error(self, message: str, function: Optional[str] = None):
        self._log("ERROR", message, function)

    def critical(self, message: str, function: Optional[str] = None):
        self._log("CRITICAL", message, function)


class R2RLoggingProvider:
    _instance = None
    _is_configured = False
    _config: Optional[LoggingConfig] = None

    PERSISTENT_PROVIDERS = {
        "r2r": SqlitePersistentLoggingProvider,
        # TODO - Mark this as deprecated
        "local": SqlitePersistentLoggingProvider,
    }

    @classmethod
    def get_persistent_logger(cls):
        return cls.PERSISTENT_PROVIDERS[cls._config.provider](cls._config)

    @classmethod
    def configure(cls, logging_config: LoggingConfig):
        if logging_config.provider == "local":
            logger.warning(
                "Local logging provider is deprecated. Please use 'r2r' instead."
            )
        if not cls._is_configured:
            cls._config = logging_config
            cls._is_configured = True
        else:
            raise Exception("R2RLoggingProvider is already configured.")

    @classmethod
    async def log(
        cls,
        run_id: UUID,
        key: str,
        value: str,
    ):
        try:
            async with cls.get_persistent_logger() as provider:
                await provider.log(run_id, key, value)
        except Exception as e:
            logger.error(f"Error logging data {(run_id, key, value)}: {e}")

    @classmethod
    async def info_log(
        cls,
        run_id: UUID,
        run_type: RunType,
        user_id: UUID,
    ):
        try:
            async with cls.get_persistent_logger() as provider:
                await provider.info_log(run_id, run_type, user_id)
        except Exception as e:
            logger.error(
                f"Error logging info data {(run_id, run_type, user_id)}: {e}"
            )

    @classmethod
    async def get_info_logs(
        cls,
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        async with cls.get_persistent_logger() as provider:
            return await provider.get_info_logs(
                offset=offset,
                limit=limit,
                run_type_filter=run_type_filter,
                user_ids=user_ids,
            )

    @classmethod
    async def get_logs(
        cls,
        run_ids: list[UUID],
        limit_per_run: int = 10,
    ) -> list:
        async with cls.get_persistent_logger() as provider:
            return await provider.get_logs(run_ids, limit_per_run)

    @classmethod
    async def create_conversation(cls) -> str:
        async with cls.get_persistent_logger() as provider:
            return await provider.create_conversation()

    @classmethod
    async def get_conversations_overview(
        cls,
        conversation_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        async with cls.get_persistent_logger() as provider:
            return await provider.get_conversations_overview(
                conversation_ids=conversation_ids,
                offset=offset,
                limit=limit,
            )

    @classmethod
    async def add_message(
        cls,
        conversation_id: str,
        content: Message,
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        async with cls.get_persistent_logger() as provider:
            return await provider.add_message(
                conversation_id, content, parent_id, metadata
            )

    @classmethod
    async def edit_message(
        cls, message_id: str, new_content: str
    ) -> Tuple[str, str]:
        async with cls.get_persistent_logger() as provider:
            return await provider.edit_message(message_id, new_content)

    @classmethod
    async def get_conversation(
        cls, conversation_id: str, branch_id: Optional[str] = None
    ) -> list[dict]:
        async with cls.get_persistent_logger() as provider:
            return await provider.get_conversation(conversation_id, branch_id)

    @classmethod
    async def get_branches_overview(cls, conversation_id: str) -> list[dict]:
        async with cls.get_persistent_logger() as provider:
            return await provider.get_branches_overview(conversation_id)

    @classmethod
    async def get_next_branch(cls, current_branch_id: str) -> Optional[str]:
        async with cls.get_persistent_logger() as provider:
            return await provider.get_next_branch(current_branch_id)

    @classmethod
    async def get_prev_branch(cls, current_branch_id: str) -> Optional[str]:
        async with cls.get_persistent_logger() as provider:
            return await provider.get_prev_branch(current_branch_id)

    @classmethod
    async def branch_at_message(cls, message_id: str) -> str:
        async with cls.get_persistent_logger() as provider:
            return await provider.branch_at_message(message_id)

    @classmethod
    async def delete_conversation(cls, conversation_id: str):
        async with cls.get_persistent_logger() as provider:
            await provider.delete_conversation(conversation_id)

    @classmethod
    async def close(cls):
        async with cls.get_persistent_logger() as provider:
            await provider.close()
