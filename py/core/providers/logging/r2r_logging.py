from typing import Optional, Tuple
from uuid import UUID

from core.base import Message
from core.base.logging.base import RunType
from core.base.logging.r2r_logger import (
    LoggingConfig,
    RunInfoLog,
    SqlitePersistentLoggingProvider,
    logger,
)


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
