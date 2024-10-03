import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import asyncpg
import yaml

from core.base import DatabaseProvider, Prompt, PromptConfig, PromptProvider
from core.base.utils import generate_default_prompt_id

logger = logging.getLogger(__name__)


class R2RPromptProvider(PromptProvider):
    def __init__(self, config: PromptConfig, db_provider: DatabaseProvider):
        super().__init__(config)
        self.prompts: dict[str, Prompt] = {}
        self.config: PromptConfig = config
        self.db_provider = db_provider
        self.pool: Optional[asyncpg.pool.Pool] = None  # Initialize pool

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._close_connection()

    async def _close_connection(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def initialize(self):
        try:
            self.pool = await asyncpg.create_pool(
                self.db_provider.connection_string
            )
            logger.info(
                "R2RPromptProvider successfully connected to Postgres database."
            )

            async with self.pool.acquire() as conn:
                await conn.execute('CREATE EXTENSION IF NOT EXISTS "lo";')

            await self.create_table()
            await self._load_prompts_from_database()
            await self._load_prompts_from_yaml_directory()
        except Exception as e:
            logger.error(f"Failed to initialize R2RPromptProvider: {e}")
            raise

    def _get_table_name(self, base_name: str) -> str:
        return self.db_provider._get_table_name(base_name)

    async def create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('prompts')} (
            prompt_id UUID PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            template TEXT NOT NULL,
            input_types JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        try:
            await self.execute_query(query)
            logger.debug("Prompts table ensured in the database.")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise

    async def execute_query(
        self, query: str, params: Optional[list[Any]] = None
    ) -> Any:
        if not self.pool:
            raise ConnectionError("Database pool is not initialized.")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if params:
                    return await conn.execute(query, *params)
                return await conn.execute(query)

    async def fetch_query(
        self, query: str, params: Optional[list[Any]] = None
    ) -> Any:
        if not self.pool:
            raise ConnectionError("Database pool is not initialized.")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                return (
                    await conn.fetch(query, *params)
                    if params
                    else await conn.fetch(query)
                )

    # FIXME: We really should be taking advantage of Pydantic models here
    # so that we don't have to json.dumps/loads all the time
    async def _load_prompts_from_database(self):
        query = f"""
        SELECT prompt_id, name, template, input_types, created_at, updated_at
        FROM {self._get_table_name("prompts")}
        """
        try:
            results = await self.fetch_query(query)
            for row in results:
                (
                    _,
                    name,
                    template,
                    input_types,
                    created_at,
                    updated_at,
                ) = (
                    row["prompt_id"],
                    row["name"],
                    row["template"],
                    json.loads(row["input_types"]),
                    row["created_at"],
                    row["updated_at"],
                )
                self.prompts[name] = Prompt(
                    name=name,
                    template=template,
                    input_types=input_types,
                    created_at=created_at,
                    updated_at=updated_at,
                )
            logger.debug(
                f"Loaded {len(self.prompts)} prompts from the database."
            )
        except Exception as e:
            logger.error(f"Failed to load prompts from database: {e}")
            raise

    async def _load_prompts_from_yaml_directory(
        self, directory_path: Optional[Path] = None
    ):
        if not directory_path:
            directory_path = (
                self.config.file_path
                or Path(os.path.dirname(__file__)) / "defaults"
            )

        if not directory_path.is_dir():
            error_msg = (
                f"The specified path is not a directory: {directory_path}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Loading prompts from {directory_path}")
        for yaml_file in directory_path.glob("*.yaml"):
            logger.debug(f"Loading prompts from {yaml_file}")
            try:
                with open(yaml_file, "r") as file:
                    data = yaml.safe_load(file)
                    if not isinstance(data, dict):
                        raise ValueError(
                            f"Invalid format in YAML file {yaml_file}"
                        )
                    for name, prompt_data in data.items():
                        if name not in self.prompts:
                            modify_prompt = True
                        else:
                            modify_prompt = (
                                self.prompts[name].created_at
                                == self.prompts[name].updated_at
                            )

                        if modify_prompt:
                            await self.add_prompt(
                                name,
                                prompt_data["template"],
                                prompt_data.get("input_types", {}),
                                modify_created_at=True,
                            )
            except yaml.YAMLError as e:
                error_msg = (
                    f"Error loading prompts from YAML file {yaml_file}: {e}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            except KeyError as e:
                error_msg = f"Missing key in YAML file {yaml_file}: {e}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            except Exception as e:
                error_msg = (
                    f"Unexpected error loading YAML file {yaml_file}: {e}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

    async def add_prompt(
        self,
        name: str,
        template: str,
        input_types: dict[str, str],
        modify_created_at: bool = False,
    ) -> None:
        prompt = Prompt(
            prompt_id=generate_default_prompt_id(name),
            name=name,
            template=template,
            input_types=input_types,
        )
        self.prompts[name] = prompt
        try:
            await self._save_prompt_to_database(
                prompt, modify_created_at=modify_created_at
            )
            logger.debug(f"Added/Updated prompt '{name}' successfully.")
        except Exception as e:
            logger.error(f"Failed to add/update prompt '{name}': {e}")
            raise

    def get_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> str:
        if prompt_name not in self.prompts:
            raise ValueError(f"Prompt '{prompt_name}' not found.")
        existing_types = self.prompts[prompt_name].input_types
        prompt = (
            Prompt(
                name=prompt_name,
                template=prompt_override,
                input_types=existing_types,
            )
            if prompt_override
            else self.prompts[prompt_name]
        )
        return (
            prompt.template if inputs is None else prompt.format_prompt(inputs)
        )

    async def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        if name not in self.prompts:
            raise ValueError(f"Prompt '{name}' not found.")
        prompt = self.prompts[name]
        if template:
            prompt.template = template
        if input_types:
            prompt.input_types = input_types
        try:
            await self._save_prompt_to_database(prompt)
            logger.info(f"Updated prompt '{name}' successfully.")
        except Exception as e:
            logger.error(f"Failed to update prompt '{name}': {e}")
            raise

    def get_all_prompts(self) -> dict[str, Prompt]:
        return self.prompts

    async def delete_prompt(self, name: str) -> None:
        if name not in self.prompts:
            raise ValueError(f"Prompt '{name}' not found.")
        del self.prompts[name]
        query = f"""
        DELETE FROM {self._get_table_name('prompts')}
        WHERE name = $1
        """
        try:
            await self.execute_query(query, [name])
            logger.info(f"Deleted prompt '{name}' successfully.")
        except Exception as e:
            logger.error(f"Failed to delete prompt '{name}': {e}")
            raise

    async def _save_prompt_to_database(
        self, prompt: Prompt, modify_created_at: bool = False
    ):
        try:
            created_at_clause = (
                "created_at = NOW()," if modify_created_at else ""
            )

            query = f"""
            INSERT INTO {self._get_table_name('prompts')}
            (prompt_id, name, template, input_types)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (name) DO UPDATE SET
                template = EXCLUDED.template,
                input_types = EXCLUDED.input_types,
                {created_at_clause}
                updated_at = NOW();
            """
            await self.execute_query(
                query,
                [
                    generate_default_prompt_id(prompt.name),
                    prompt.name,
                    prompt.template,
                    json.dumps(prompt.input_types),
                ],
            )
        except Exception as e:
            logger.error(
                f"Failed to save prompt '{prompt.name}' to database: {e}"
            )
            raise
