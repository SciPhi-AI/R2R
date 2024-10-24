import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
from uuid import UUID

from core.base import PromptHandler


class PostgresPromptHandler(PromptHandler):
    """PostgreSQL implementation of the PromptHandler."""

    async def create_tables(self):
        """Create the necessary tables for storing prompts."""
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name("prompts")} (
            name VARCHAR(255) PRIMARY KEY,
            template TEXT NOT NULL,
            input_types JSONB NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        CREATE OR REPLACE FUNCTION {self.project_name}.update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';

        DROP TRIGGER IF EXISTS update_prompts_updated_at
        ON {self._get_table_name("prompts")};

        CREATE TRIGGER update_prompts_updated_at
            BEFORE UPDATE ON {self._get_table_name("prompts")}
            FOR EACH ROW
            EXECUTE FUNCTION {self.project_name}.update_updated_at_column();
        """
        await self.connection_manager.execute_query(query)

    async def add_prompt(
        self, name: str, template: str, input_types: dict[str, str]
    ) -> None:
        """Add a new prompt template to the database."""
        query = f"""
        INSERT INTO {self._get_table_name("prompts")} (name, template, input_types)
        VALUES ($1, $2, $3)
        ON CONFLICT (name) DO UPDATE
        SET template = EXCLUDED.template,
            input_types = EXCLUDED.input_types;
        """
        await self.connection_manager.execute_query(
            query, [name, template, json.dumps(input_types)]
        )

    async def get_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> str:
        """Retrieve and format a prompt template."""
        if prompt_override:
            return prompt_override

        query = f"""
        SELECT template, input_types
        FROM {self._get_table_name("prompts")}
        WHERE name = $1;
        """
        result = await self.connection_manager.fetchrow_query(
            query, [prompt_name]
        )

        if not result:
            raise ValueError(f"Prompt template '{prompt_name}' not found")

        template = result["template"]
        input_types = result["input_types"]

        if inputs:
            # Validate input types match the schema
            for key, value in inputs.items():
                expected_type = input_types.get(key)
                if not expected_type:
                    raise ValueError(f"Unexpected input key: {key}")
                # Add more type validation if needed

            # Format the template with the provided inputs
            return template.format(**inputs)

        return template

    async def get_all_prompts(self) -> dict[str, Any]:
        """Retrieve all stored prompts."""
        query = f"""
        SELECT name, template, input_types, created_at, updated_at
        FROM {self._get_table_name("prompts")};
        """
        results = await self.connection_manager.fetch_query(query)

        prompts = {}
        for row in results:
            prompts[row["name"]] = {
                "template": row["template"],
                "input_types": row["input_types"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        return prompts

    async def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        """Update an existing prompt template."""
        if not template and not input_types:
            return

        updates = []
        params = [name]
        if template:
            updates.append(f"template = ${len(params) + 1}")
            params.append(template)
        if input_types:
            updates.append(f"input_types = ${len(params) + 1}")
            params.append(json.dumps(input_types))

        query = f"""
        UPDATE {self._get_table_name("prompts")}
        SET {', '.join(updates)}
        WHERE name = $1;
        """
        result = await self.connection_manager.execute_query(query, params)
        if result == "UPDATE 0":
            raise ValueError(f"Prompt template '{name}' not found")

    async def delete_prompt(self, name: str) -> None:
        """Delete a prompt template."""
        query = f"""
        DELETE FROM {self._get_table_name("prompts")}
        WHERE name = $1;
        """
        result = await self.connection_manager.execute_query(query, [name])
        if result == "DELETE 0":
            raise ValueError(f"Prompt template '{name}' not found")

    async def get_message_payload(
        self,
        system_prompt_name: Optional[str] = None,
        system_role: str = "system",
        system_inputs: dict = {},
        system_prompt_override: Optional[str] = None,
        task_prompt_name: Optional[str] = None,
        task_role: str = "user",
        task_inputs: dict = {},
        task_prompt_override: Optional[str] = None,
    ) -> list[dict]:
        """Create a message payload from system and task prompts."""
        if system_prompt_override:
            system_prompt = system_prompt_override
        else:
            system_prompt = await self.get_prompt(
                system_prompt_name or "default_system",
                system_inputs,
                prompt_override=system_prompt_override,
            )

        task_prompt = await self.get_prompt(
            task_prompt_name or "default_rag",
            task_inputs,
            prompt_override=task_prompt_override,
        )

        return [
            {
                "role": system_role,
                "content": system_prompt,
            },
            {
                "role": task_role,
                "content": task_prompt,
            },
        ]
