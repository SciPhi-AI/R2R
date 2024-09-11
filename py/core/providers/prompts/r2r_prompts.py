import json
import logging
import os
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import yaml
from sqlalchemy import text

from core.base import Prompt, PromptConfig, PromptProvider, R2RException
from core.providers.database.postgres import PostgresDBProvider

logger = logging.getLogger(__name__)


class R2RPromptProvider(PromptProvider):
    def __init__(self, config: PromptConfig, db_provider: PostgresDBProvider):
        super().__init__(config)
        self.prompts: dict[str, Prompt] = {}
        self.config = config
        self.db_provider = db_provider
        self.create_table()
        self._load_prompts_from_database()
        self._load_prompts_from_yaml_directory()

    def _get_table_name(self, base_name: str) -> str:
        return f"{base_name}"

    def execute_query(
        self, query: str, params: Optional[dict[str, Any]] = None
    ) -> Any:
        return self.db_provider.relational.execute_query(query, params)

    def create_table(self):
        query = text(
            f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name('prompts')} (
                prompt_id UUID PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                template TEXT NOT NULL,
                input_types JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        try:
            self.execute_query(query)
            logger.info(f"Created table {self._get_table_name('prompts')}")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise

    def _load_prompts_from_database(self):
        query = text(
            f"""
            SELECT prompt_id, name, template, input_types
            FROM {self._get_table_name('prompts')}
            """
        )
        results = self.execute_query(query).fetchall()
        for row in results:
            prompt_id, name, template, input_types = row
            self.prompts[name] = Prompt(
                name=name, template=template, input_types=input_types
            )

    def _load_prompts_from_yaml_directory(
        self, directory_path: Optional[Path] = None
    ):
        if not directory_path:
            directory_path = (
                self.config.file_path
                or Path(os.path.dirname(__file__)) / "defaults"
            )

        if not directory_path.is_dir():
            raise ValueError(
                f"The specified path is not a directory: {directory_path}"
            )

        logger.info(f"Loading prompts from {directory_path}")
        for yaml_file in directory_path.glob("*.yaml"):
            logger.debug(f"Loading prompts from {yaml_file}")
            try:
                with open(yaml_file, "r") as file:
                    data = yaml.safe_load(file)
                    for name, prompt_data in data.items():
                        if name not in self.prompts:
                            self.add_prompt(
                                name,
                                prompt_data["template"],
                                prompt_data.get("input_types", {}),
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

    def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> None:
        if name in self.prompts:
            raise ValueError(f"Prompt '{name}' already exists.")
        prompt = Prompt(name=name, template=template, input_types=input_types)
        self.prompts[name] = prompt
        self._save_prompt_to_database(prompt)

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
        if inputs is None:
            return prompt.template
        return prompt.format_prompt(inputs)

    def update_prompt(
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
        self._save_prompt_to_database(prompt)

    def get_all_prompts(self) -> dict[str, Prompt]:
        return [v.dict() for v in self.prompts.values()]

    def delete_prompt(self, name: str) -> None:
        if name not in self.prompts:
            raise ValueError(f"Prompt '{name}' not found.")
        del self.prompts[name]
        query = text(
            f"""
            DELETE FROM {self._get_table_name('prompts')}
            WHERE name = :name
            """
        )
        self.execute_query(query, {"name": name})

    def _save_prompt_to_database(self, prompt: Prompt):
        query = text(
            f"""
            INSERT INTO {self._get_table_name('prompts')}
            (prompt_id, name, template, input_types)
            VALUES (:prompt_id, :name, :template, :input_types)
            ON CONFLICT (name) DO UPDATE SET
                template = EXCLUDED.template,
                input_types = EXCLUDED.input_types,
                updated_at = NOW();
            """
        )
        result = self.execute_query(
            query,
            {
                "prompt_id": uuid4(),
                "name": prompt.name,
                "template": prompt.template,
                "input_types": json.dumps(prompt.input_types),
            },
        )
        if not result:
            raise R2RException(
                status_code=500,
                message=f"Failed to upsert prompt {prompt.name}",
            )
