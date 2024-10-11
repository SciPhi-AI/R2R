import json
import logging
import os
from abc import abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from core.base import Message

from ..providers.base import Provider, ProviderConfig
from .base import RunType

logger = logging.getLogger(__name__)

import uuid
from typing import Dict, List, Optional, Tuple


class ConversationManager:
    def __init__(self, conn):
        import aiosqlite

        self.conn: aiosqlite = conn

    async def _init(self):
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT,
                conversation_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT,
                conversation_id TEXT,
                parent_id TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (parent_id) REFERENCES messages(id)
            );

            CREATE TABLE IF NOT EXISTS branches (
                id TEXT,
                conversation_id TEXT,
                branch_point_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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

    async def create_conversation(self) -> str:
        print("a")
        conversation_id = str(uuid.uuid4())
        await self.conn.execute(
            "INSERT INTO conversations (conversation_id) VALUES (?)",
            (conversation_id,),
        )

        print("b")
        # Create initial branch for the conversation
        branch_id = str(uuid.uuid4())
        await self.conn.execute(
            "INSERT INTO branches (id, conversation_id, branch_point_id) VALUES (?, ?, NULL)",
            (branch_id, conversation_id),
        )

        print("c")
        await self.conn.commit()
        print("d")
        return conversation_id

    async def add_message(
        self,
        conversation_id: str,
        content: Message,
        parent_id: Optional[str] = None,
    ) -> str:
        print("az")
        message_id = str(uuid.uuid4())
        print("message_id = ", message_id)
        print("conversation_id = ", conversation_id)
        print("parent_id = ", parent_id)
        print("content = ", content)
        print("content.json = ", content.json())
        await self.conn.execute(
            """
            INSERT INTO messages (id, conversation_id, parent_id, content)
            VALUES (?, ?, ?, ?)
        """,
            (message_id, conversation_id, parent_id, content.json()),
        )

        if parent_id is not None:
            print("bz")

            # Get the branch_id(s) of the parent message
            cursor = await self.conn.execute(
                """
                SELECT branch_id FROM message_branches
                WHERE message_id = ?
                ORDER BY branch_id DESC
                LIMIT 1
            """,
                (parent_id,),
            )
            branch_id_row = await cursor.fetchone()
            if branch_id_row:
                branch_id = branch_id_row[0]
            else:
                print("cz")

                # If parent message is not linked to any branch, use the most recent branch
                cursor = await self.conn.execute(
                    """
                    SELECT id FROM branches
                    WHERE conversation_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """,
                    (conversation_id,),
                )
                branch_id = (await cursor.fetchone())[0]
        else:
            print("dz")

            # For messages with no parent, use the most recent branch
            cursor = await self.conn.execute(
                """
                SELECT id FROM branches
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (conversation_id,),
            )
            branch_id = (await cursor.fetchone())[0]

        # Link the new message to the same branch as its parent
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO message_branches (message_id, branch_id)
            VALUES (?, ?)
        """,
            (message_id, branch_id),
        )

        await self.conn.commit()
        return message_id

    async def edit_message(
        self, message_id: int, new_content: str
    ) -> Tuple[int, int]:
        # Get the original message details
        await self.conn.execute(
            "SELECT conversation_id, parent_id FROM messages WHERE id = ?",
            (message_id,),
        )
        conversation_id, parent_id = await self.conn.fetchone()

        # Create a new branch
        await self.conn.execute(
            """
            INSERT INTO branches (conversation_id, branch_point_id)
            VALUES (?, ?)
        """,
            (conversation_id, message_id),
        )
        new_branch_id = str(uuid.uuid4())  # await self.conn.lastrowid

        # Add the edited message with the same parent_id
        await self.conn.execute(
            """
            INSERT INTO messages (conversation_id, parent_id, content)
            VALUES (?, ?, ?)
        """,
            (conversation_id, parent_id, new_content),
        )
        new_message_id = await self.conn.lastrowid

        # Link the new message to the new branch
        await self.conn.execute(
            """
            INSERT INTO message_branches (message_id, branch_id)
            VALUES (?, ?)
        """,
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

        # Do NOT link descendants to the new branch or update their parent_ids

        await self.conn.commit()
        return new_message_id, new_branch_id

    async def get_conversation(
        self, conversation_id: int, branch_id: Optional[int] = None
    ) -> List[Dict]:
        if branch_id is None:
            # Get the most recent branch by ID
            await self.conn.execute(
                """
                SELECT id FROM branches
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT 1
            """,
                (conversation_id,),
            )
            branch_id = str(uuid.uuid4())  # await self.conn.fetchone()[0]

        # Get all messages for this branch
        async with self.conn.execute(
            """
            WITH RECURSIVE branch_messages(id, content, parent_id, depth) AS (
                SELECT DISTINCT m.id, m.content, m.parent_id, 0
                FROM messages m
                JOIN message_branches mb ON m.id = mb.message_id
                LEFT JOIN message_branches mbp ON m.parent_id = mbp.message_id AND mbp.branch_id = mb.branch_id
                WHERE mb.branch_id = ? AND (m.parent_id IS NULL OR mbp.branch_id IS NOT NULL)
                UNION
                SELECT DISTINCT m.id, m.content, m.parent_id, bm.depth + 1
                FROM messages m
                JOIN message_branches mb ON m.id = mb.message_id
                JOIN branch_messages bm ON m.parent_id = bm.id
                WHERE mb.branch_id = ?
            )
            SELECT DISTINCT id, content, parent_id FROM branch_messages
            ORDER BY depth, id
        """,
            (branch_id, branch_id),
        ) as cursor:
            rows = await cursor.fetchall()
            messages = [
                {"id": row[0], "content": row[1], "parent_id": row[2]}
                for row in rows
            ]
            return messages

        # # Get all messages for this branch
        # await self.conn.execute('''
        #     WITH RECURSIVE branch_messages(id, content, parent_id, depth) AS (
        #         SELECT DISTINCT m.id, m.content, m.parent_id, 0
        #         FROM messages m
        #         JOIN message_branches mb ON m.id = mb.message_id
        #         LEFT JOIN message_branches mbp ON m.parent_id = mbp.message_id AND mbp.branch_id = mb.branch_id
        #         WHERE mb.branch_id = ? AND (m.parent_id IS NULL OR mbp.branch_id IS NOT NULL)
        #         UNION
        #         SELECT DISTINCT m.id, m.content, m.parent_id, bm.depth + 1
        #         FROM messages m
        #         JOIN message_branches mb ON m.id = mb.message_id
        #         JOIN branch_messages bm ON m.parent_id = bm.id
        #         WHERE mb.branch_id = ?
        #     )
        #     SELECT DISTINCT id, content, parent_id FROM branch_messages
        #     ORDER BY depth, id
        # ''', (branch_id, branch_id))

        # messages = [{'id': row[0], 'content': row[1], 'parent_id': row[2]} for row in (await self.conn.fetchall())]
        # return messages

    # async def list_branches(self, conversation_id: int) -> List[Dict]:
    #     await self.conn.execute('''
    #         SELECT b.id, b.branch_point_id, m.content, b.created_at
    #         FROM branches b
    #         LEFT JOIN messages m ON b.branch_point_id = m.id
    #         WHERE b.conversation_id = ?
    #         ORDER BY b.created_at
    #     ''', (conversation_id,))
    #     return [{
    #         'branch_id': row[0],
    #         'branch_point_id': row[1],
    #         'content': row[2],
    #         'created_at': row[3]
    #     } for row in self.conn.fetchall()]

    async def list_branches(self, conversation_id: int) -> List[Dict]:
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

    async def get_next_branch(self, current_branch_id: int) -> Optional[int]:
        await self.conn.execute(
            """
            SELECT id FROM branches
            WHERE conversation_id = (SELECT conversation_id FROM branches WHERE id = ?)
            AND id > ?
            ORDER BY id
            LIMIT 1
        """,
            (current_branch_id, current_branch_id),
        )

        result = self.conn.fetchone()
        return result[0] if result else None

    async def get_prev_branch(self, current_branch_id: int) -> Optional[int]:
        self.conn.execute(
            """
            SELECT id FROM branches
            WHERE conversation_id = (SELECT conversation_id FROM branches WHERE id = ?)
            AND id < ?
            ORDER BY id DESC
            LIMIT 1
        """,
            (current_branch_id, current_branch_id),
        )

        result = await self.conn.fetchone()
        return result[0] if result else None

    async def branch_at_message(self, message_id: int) -> int:
        await self.conn.execute(
            "SELECT conversation_id FROM messages WHERE id = ?", (message_id,)
        )
        conversation_id = await self.conn.fetchone()[0]

        # Create a new branch starting from message_id
        await self.conn.execute(
            """
            INSERT INTO branches (conversation_id, branch_point_id)
            VALUES (?, ?)
        """,
            (conversation_id, message_id),
        )
        new_branch_id = str(uuid.uuid4())  # self.conn.lastrowid

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

    async def close(self):
        await self.conn.close()


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


class LocalRunLoggingProvider(RunLoggingProvider):
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
                "Please install aiosqlite to use the LocalRunLoggingProvider."
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
        await self.conn.commit()
        self.conversation_manager = ConversationManager(self.conn)
        print("self.conversation_manager = ", self.conversation_manager)
        print("~~~" * 500)
        await self.conversation_manager._init()

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


class PostgresLoggingConfig(LoggingConfig):
    provider: str = "postgres"
    log_table: str = "logs"
    log_info_table: str = "log_info"

    def validate_config(self) -> None:
        required_env_vars = [
            "POSTGRES_DBNAME",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_HOST",
            "POSTGRES_PORT",
        ]
        for var in required_env_vars:
            if not os.getenv(var):
                raise ValueError(f"Environment variable {var} is not set.")

    @property
    def supported_providers(self) -> list[str]:
        return ["postgres"]


class PostgresRunLoggingProvider(RunLoggingProvider):
    def __init__(self, config: PostgresLoggingConfig):
        self.log_table = config.log_table
        self.log_info_table = config.log_info_table
        self.config = config
        self.project_name = config.app.project_name or os.getenv(
            "R2R_PROJECT_NAME", "r2r_default"
        )
        self.pool = None
        if not os.getenv("POSTGRES_DBNAME"):
            raise ValueError(
                "Please set the environment variable POSTGRES_DBNAME."
            )
        if not os.getenv("POSTGRES_USER"):
            raise ValueError(
                "Please set the environment variable POSTGRES_USER."
            )
        if not os.getenv("POSTGRES_PASSWORD"):
            raise ValueError(
                "Please set the environment variable POSTGRES_PASSWORD."
            )
        if not os.getenv("POSTGRES_HOST"):
            raise ValueError(
                "Please set the environment variable POSTGRES_HOST."
            )
        if not os.getenv("POSTGRES_PORT"):
            raise ValueError(
                "Please set the environment variable POSTGRES_PORT."
            )

    async def _init(self):
        self.pool = await asyncpg.create_pool(
            database=os.getenv("POSTGRES_DBNAME"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            statement_cache_size=0,  # Disable statement caching
        )
        async with self.pool.acquire() as conn:

            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.project_name}.{self.log_table} (
                    timestamp TIMESTAMPTZ,
                    run_id UUID,
                    key TEXT,
                    value TEXT
                )
                """
            )
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.project_name}.{self.log_info_table} (
                    timestamp TIMESTAMPTZ,
                    run_id UUID UNIQUE,
                    run_type TEXT,
                    user_id UUID
                )
            """
            )

    async def __aenter__(self):
        if self.pool is None:
            await self._init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def log(
        self,
        run_id: UUID,
        key: str,
        value: str,
    ):
        if not self.pool:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO {self.project_name}.{self.log_table} (timestamp, run_id, key, value) VALUES (NOW(), $1, $2, $3)",
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
        if not self.pool:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO {self.project_name}.{self.log_info_table} (timestamp, run_id, run_type, user_id) VALUES (NOW(), $1, $2, $3)",
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
        if not self.pool:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        query = f"SELECT run_id, run_type, timestamp, user_id FROM {self.project_name}.{self.log_info_table}"
        conditions = []
        params = []
        param_count = 1

        if run_type_filter:
            conditions.append(f"run_type = ${param_count}")
            params.append(run_type_filter)
            param_count += 1

        if user_ids:
            conditions.append(f"user_id = ANY(${param_count}::uuid[])")
            params.append(user_ids)
            param_count += 1

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY timestamp DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
        params.extend([limit, offset])

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                RunInfoLog(
                    run_id=row["run_id"],
                    run_type=row["run_type"],
                    timestamp=row["timestamp"],
                    user_id=row["user_id"],
                )
                for row in rows
            ]

    async def get_logs(
        self, run_ids: list[UUID], limit_per_run: int = 10
    ) -> list:
        if not run_ids:
            raise ValueError("No run ids provided.")
        if not self.pool:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        placeholders = ",".join([f"${i + 1}" for i in range(len(run_ids))])
        query = f"""
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY timestamp DESC) as rn
            FROM {self.project_name}.{self.log_table}
            WHERE run_id::text IN ({placeholders})
        ) sub
        WHERE sub.rn <= ${len(run_ids) + 1}
        ORDER BY sub.timestamp DESC
        """
        params = [str(run_id) for run_id in run_ids] + [limit_per_run]
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [{key: row[key] for key in row.keys()} for row in rows]


class RunLoggingSingleton:
    _instance = None
    _is_configured = False
    _config: Optional[LoggingConfig] = None

    SUPPORTED_PROVIDERS = {
        "local": LocalRunLoggingProvider,
        "postgres": PostgresRunLoggingProvider,
    }

    @classmethod
    def get_instance(cls):
        return cls.SUPPORTED_PROVIDERS[cls._config.provider](cls._config)

    @classmethod
    def configure(cls, logging_config: LoggingConfig):
        if not cls._is_configured:
            cls._config = logging_config
            cls._is_configured = True
        else:
            raise Exception("RunLoggingSingleton is already configured.")

    @classmethod
    async def log(
        cls,
        run_id: UUID,
        key: str,
        value: str,
    ):
        try:
            async with cls.get_instance() as provider:
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
        # try:
        #     async with cls.get_instance() as provider:
        #         await provider.info_log(run_id, run_type, user_id)
        # except Exception as e:
        #     logger.error(
        #         f"Error logging info data {(run_id, run_type, user_id)}: {e}"
        #     )
        pass

    @classmethod
    async def get_info_logs(
        cls,
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        async with cls.get_instance() as provider:
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
        async with cls.get_instance() as provider:
            return await provider.get_logs(run_ids, limit_per_run)

    @classmethod
    async def create_conversation(cls) -> str:
        async with cls.get_instance() as provider:
            return await provider.conversation_manager.create_conversation()

    @classmethod
    async def add_message(
        cls,
        conversation_id: str,
        content: str,
        parent_id: Optional[str] = None,
    ) -> str:
        async with cls.get_instance() as provider:
            return await provider.conversation_manager.add_message(
                conversation_id, content, parent_id
            )

    @classmethod
    async def edit_message(
        cls, message_id: int, new_content: str
    ) -> Tuple[int, int]:
        async with cls.get_instance() as provider:
            return await provider.conversation_manager.edit_message(
                message_id, new_content
            )

    @classmethod
    async def get_conversation(
        cls, conversation_id: int, branch_id: Optional[int] = None
    ) -> List[Dict]:
        async with cls.get_instance() as provider:
            return await provider.conversation_manager.get_conversation(
                conversation_id, branch_id
            )

    @classmethod
    async def list_branches(cls, conversation_id: int) -> List[Dict]:
        async with cls.get_instance() as provider:
            return await provider.conversation_manager.list_branches(
                conversation_id
            )

    @classmethod
    async def get_next_branch(cls, current_branch_id: int) -> Optional[int]:
        async with cls.get_instance() as provider:
            return await provider.conversation_manager.get_next_branch(
                current_branch_id
            )

    @classmethod
    async def get_prev_branch(cls, current_branch_id: int) -> Optional[int]:
        async with cls.get_instance() as provider:
            return await provider.conversation_manager.get_prev_branch(
                current_branch_id
            )

    @classmethod
    async def branch_at_message(cls, message_id: int) -> int:
        async with cls.get_instance() as provider:
            return await provider.conversation_manager.branch_at_message(
                message_id
            )

    @classmethod
    async def close(cls):
        async with cls.get_instance() as provider:
            await provider.close()
