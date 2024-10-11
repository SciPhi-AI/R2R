import json
import uuid
from enum import Enum
from typing import Dict, List, Optional, Tuple

import aiosqlite

from core.base.abstractions import Message

from .run_logger import RunLoggingSingleton


class RunType(str, Enum):
    CONVERSATION = "conversation"
    MESSAGE = "message"


class ConversationManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    async def init(self):
        self.conn = await aiosqlite.connect(self.db_path)
        self.cursor = await self.conn.cursor()
        await self._create_tables()

    async def _create_tables(self):
        await self.cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                parent_id TEXT,
                role TEXT,
                content TEXT,
                name TEXT,
                function_call TEXT,
                tool_calls TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (parent_id) REFERENCES messages(id)
            );

            CREATE TABLE IF NOT EXISTS branches (
                id TEXT PRIMARY KEY,
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

    async def create_conversation(self, title: str) -> str:
        conversation_id = str(uuid.uuid4())
        await self.cursor.execute(
            "INSERT INTO conversations (id, title) VALUES (?, ?)",
            (conversation_id, title),
        )

        # Create initial branch for the conversation
        branch_id = str(uuid.uuid4())
        await self.cursor.execute(
            "INSERT INTO branches (id, conversation_id, branch_point_id) VALUES (?, ?, NULL)",
            (branch_id, conversation_id),
        )

        await self.conn.commit()

        # Log the creation of a conversation
        await RunLoggingSingleton.info_log(
            run_id=uuid.UUID(conversation_id),
            run_type=RunType.CONVERSATION,
            user_id=uuid.uuid4(),  # Replace with actual user ID
        )

        return conversation_id

    async def add_message(
        self,
        conversation_id: str,
        message: Message,
        parent_id: Optional[str] = None,
    ) -> str:
        message_id = str(uuid.uuid4())
        function_call_json = (
            json.dumps(message.function_call)
            if message.function_call
            else None
        )
        tool_calls_json = (
            json.dumps(message.tool_calls) if message.tool_calls else None
        )

        await self.cursor.execute(
            """
            INSERT INTO messages (id, conversation_id, parent_id, content)
            VALUES (?, ?, ?, ?)
        """,
            (message_id, conversation_id, parent_id, content),
        )

        if parent_id is not None:
            # Get the branch_id(s) of the parent message
            await self.cursor.execute(
                """
                SELECT branch_id FROM message_branches
                WHERE message_id = ?
                ORDER BY branch_id DESC
                LIMIT 1
            """,
                (parent_id,),
            )
            branch_id_row = await self.cursor.fetchone()
            if branch_id_row:
                branch_id = branch_id_row[0]
            else:
                # If parent message is not linked to any branch, use the most recent branch
                await self.cursor.execute(
                    """
                    SELECT id FROM branches
                    WHERE conversation_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """,
                    (conversation_id,),
                )
                branch_id = (await self.cursor.fetchone())[0]
        else:
            # For messages with no parent, use the most recent branch
            await self.cursor.execute(
                """
                SELECT id FROM branches
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (conversation_id,),
            )
            branch_id = (await self.cursor.fetchone())[0]

        # Link the new message to the same branch as its parent
        await self.cursor.execute(
            """
            INSERT OR IGNORE INTO message_branches (message_id, branch_id)
            VALUES (?, ?)
        """,
            (message_id, branch_id),
        )

        await self.conn.commit()

        # Log the addition of a message
        await RunLoggingSingleton.log(
            run_id=uuid.UUID(conversation_id),
            key="add_message",
            value=json.dumps(
                {
                    "message_id": message_id,
                    "content": content,
                    "parent_id": parent_id,
                }
            ),
        )

        return message_id

    async def edit_message(
        self, message_id: str, new_content: str
    ) -> Tuple[str, str]:
        # Get the original message details
        await self.cursor.execute(
            "SELECT conversation_id, parent_id FROM messages WHERE id = ?",
            (message_id,),
        )
        row = await self.cursor.fetchone()
        if row is None:
            raise ValueError(f"Message with id {message_id} not found.")
        conversation_id, parent_id = row

        # Create a new branch
        new_branch_id = str(uuid.uuid4())
        await self.cursor.execute(
            """
            INSERT INTO branches (id, conversation_id, branch_point_id)
            VALUES (?, ?, ?)
        """,
            (new_branch_id, conversation_id, message_id),
        )

        # Add the edited message with the same parent_id
        new_message_id = str(uuid.uuid4())
        await self.cursor.execute(
            """
            INSERT INTO messages (id, conversation_id, parent_id, content)
            VALUES (?, ?, ?, ?)
        """,
            (new_message_id, conversation_id, parent_id, new_content),
        )

        # Link the new message to the new branch
        await self.cursor.execute(
            """
            INSERT INTO message_branches (message_id, branch_id)
            VALUES (?, ?)
        """,
            (new_message_id, new_branch_id),
        )

        # Link ancestor messages (excluding the original message) to the new branch
        await self.cursor.execute(
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

        await self.conn.commit()

        # Log the message edit
        await RunLoggingSingleton.log(
            run_id=uuid.UUID(conversation_id),
            key="edit_message",
            value=json.dumps(
                {
                    "original_message_id": message_id,
                    "new_message_id": new_message_id,
                    "new_content": new_content,
                }
            ),
        )

        return new_message_id, new_branch_id

    async def get_conversation(
        self, conversation_id: str, branch_id: Optional[str] = None
    ) -> List[Message]:
        if branch_id is None:
            # Get the most recent branch by ID
            cursor = await self.conn.execute(
                """
                SELECT id FROM branches
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT 1
            """,
                (conversation_id,),
            )
            branch_row = await cursor.fetchone()
            if not branch_row:
                return []
            branch_id = branch_row[0]

        # Get all messages for this branch
        cursor = await self.conn.execute(
            """
            WITH RECURSIVE branch_messages(id, role, content, name, function_call, tool_calls, parent_id, depth) AS (
                SELECT DISTINCT m.id, m.role, m.content, m.name, m.function_call, m.tool_calls, m.parent_id, 0
                FROM messages m
                JOIN message_branches mb ON m.id = mb.message_id
                LEFT JOIN message_branches mbp ON m.parent_id = mbp.message_id AND mbp.branch_id = mb.branch_id
                WHERE mb.branch_id = ? AND (m.parent_id IS NULL OR mbp.branch_id IS NOT NULL)
                UNION
                SELECT DISTINCT m.id, m.role, m.content, m.name, m.function_call, m.tool_calls, m.parent_id, bm.depth + 1
                FROM messages m
                JOIN message_branches mb ON m.id = mb.message_id
                JOIN branch_messages bm ON m.parent_id = bm.id
                WHERE mb.branch_id = ?
            )
            SELECT DISTINCT id, role, content, name, function_call, tool_calls, parent_id FROM branch_messages
            ORDER BY depth, id
        """,
            (branch_id, branch_id),
        )

        rows = await cursor.fetchall()
        messages = []
        for row in rows:
            function_call = json.loads(row[4]) if row[4] else None
            tool_calls = json.loads(row[5]) if row[5] else None
            message = Message(
                role=row[1],
                content=row[2],
                name=row[3],
                function_call=function_call,
                tool_calls=tool_calls,
            )
            messages.append(message)
        return messages

    async def list_branches(self, conversation_id: str) -> List[Dict]:
        await self.cursor.execute(
            """
            SELECT b.id, b.branch_point_id, m.content, b.created_at
            FROM branches b
            LEFT JOIN messages m ON b.branch_point_id = m.id
            WHERE b.conversation_id = ?
            ORDER BY b.created_at
        """,
            (conversation_id,),
        )
        rows = await self.cursor.fetchall()
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
        await self.cursor.execute(
            """
            SELECT id FROM branches
            WHERE conversation_id = (SELECT conversation_id FROM branches WHERE id = ?)
            AND id > ?
            ORDER BY id
            LIMIT 1
        """,
            (current_branch_id, current_branch_id),
        )

        result = await self.cursor.fetchone()
        return result[0] if result else None

    async def get_prev_branch(self, current_branch_id: str) -> Optional[str]:
        await self.cursor.execute(
            """
            SELECT id FROM branches
            WHERE conversation_id = (SELECT conversation_id FROM branches WHERE id = ?)
            AND id < ?
            ORDER BY id DESC
            LIMIT 1
        """,
            (current_branch_id, current_branch_id),
        )

        result = await self.cursor.fetchone()
        return result[0] if result else None

    async def branch_at_message(self, message_id: str) -> str:
        await self.cursor.execute(
            "SELECT conversation_id FROM messages WHERE id = ?", (message_id,)
        )
        row = await self.cursor.fetchone()
        if row is None:
            raise ValueError(f"Message with id {message_id} not found.")
        conversation_id = row[0]

        # Create a new branch starting from message_id
        new_branch_id = str(uuid.uuid4())
        await self.cursor.execute(
            """
            INSERT INTO branches (id, conversation_id, branch_point_id)
            VALUES (?, ?, ?)
        """,
            (new_branch_id, conversation_id, message_id),
        )

        # Link ancestor messages to the new branch
        await self.cursor.execute(
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

        # Log the creation of a new branch
        await RunLoggingSingleton.log(
            run_id=uuid.UUID(conversation_id),
            key="branch_at_message",
            value=json.dumps(
                {"message_id": message_id, "new_branch_id": new_branch_id}
            ),
        )

        return new_branch_id

    async def close(self):
        await self.conn.close()
