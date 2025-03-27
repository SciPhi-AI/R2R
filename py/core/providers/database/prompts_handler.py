import json
import logging
import os
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar

import yaml

from core.base import Handler, generate_default_prompt_id

from .base import PostgresConnectionManager

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Represents a cached item with metadata."""

    value: T
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0


class Cache(Generic[T]):
    """A generic cache implementation with TTL and LRU-like features."""

    def __init__(
        self,
        ttl: Optional[timedelta] = None,
        max_size: Optional[int] = 1000,
        cleanup_interval: timedelta = timedelta(hours=1),
    ):
        self._cache: dict[str, CacheEntry[T]] = {}
        self._ttl = ttl
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = datetime.now()

    def get(self, key: str) -> Optional[T]:
        """Retrieve an item from cache."""
        self._maybe_cleanup()

        if key not in self._cache:
            return None

        entry = self._cache[key]

        if self._ttl and datetime.now() - entry.created_at > self._ttl:
            del self._cache[key]
            return None

        entry.last_accessed = datetime.now()
        entry.access_count += 1
        return entry.value

    def set(self, key: str, value: T) -> None:
        """Store an item in cache."""
        self._maybe_cleanup()

        now = datetime.now()
        self._cache[key] = CacheEntry(
            value=value, created_at=now, last_accessed=now
        )

        if self._max_size and len(self._cache) > self._max_size:
            self._evict_lru()

    def invalidate(self, key: str) -> None:
        """Remove an item from cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()

    def _maybe_cleanup(self) -> None:
        """Periodically clean up expired entries."""
        now = datetime.now()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup()
            self._last_cleanup = now

    def _cleanup(self) -> None:
        """Remove expired entries."""
        if not self._ttl:
            return

        now = datetime.now()
        expired = [
            k for k, v in self._cache.items() if now - v.created_at > self._ttl
        ]
        for k in expired:
            del self._cache[k]

    def _evict_lru(self) -> None:
        """Remove least recently used item."""
        if not self._cache:
            return

        lru_key = min(
            self._cache.keys(), key=lambda k: self._cache[k].last_accessed
        )
        del self._cache[lru_key]


class CacheablePromptHandler(Handler):
    """Abstract base class that adds caching capabilities to prompt
    handlers."""

    def __init__(
        self,
        cache_ttl: Optional[timedelta] = timedelta(hours=1),
        max_cache_size: Optional[int] = 1000,
    ):
        self._prompt_cache = Cache[str](ttl=cache_ttl, max_size=max_cache_size)
        self._template_cache = Cache[dict](
            ttl=cache_ttl, max_size=max_cache_size
        )

    def _cache_key(
        self, prompt_name: str, inputs: Optional[dict] = None
    ) -> str:
        """Generate a cache key for a prompt request."""
        if inputs:
            # Sort dict items for consistent keys
            sorted_inputs = sorted(inputs.items())
            return f"{prompt_name}:{sorted_inputs}"
        return prompt_name

    async def get_cached_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
        bypass_cache: bool = False,
    ) -> str:
        if prompt_override:
            # If the user gave us a direct override, use it.
            if inputs:
                try:
                    return prompt_override.format(**inputs)
                except KeyError:
                    return prompt_override
            return prompt_override

        cache_key = self._cache_key(prompt_name, inputs)

        # If not bypassing, try returning from the prompt-level cache
        if not bypass_cache:
            cached = self._prompt_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Prompt cache hit: {cache_key}")
                return cached

        logger.debug(
            "Prompt cache miss or bypass. Retrieving from DB or template cache."
        )
        # Notice the new parameter `bypass_template_cache` below
        result = await self._get_prompt_impl(
            prompt_name, inputs, bypass_template_cache=bypass_cache
        )
        self._prompt_cache.set(cache_key, result)
        return result

    async def get_prompt(  # type: ignore
        self,
        name: str,
        inputs: Optional[dict] = None,
        prompt_override: Optional[str] = None,
    ) -> dict:
        query = f"""
        SELECT id, name, template, input_types, created_at, updated_at
        FROM {self._get_table_name("prompts")}
        WHERE name = $1;
        """
        result = await self.connection_manager.fetchrow_query(query, [name])

        if not result:
            raise ValueError(f"Prompt template '{name}' not found")

        input_types = result["input_types"]
        if isinstance(input_types, str):
            input_types = json.loads(input_types)

        return {
            "id": result["id"],
            "name": result["name"],
            "template": result["template"],
            "input_types": input_types,
            "created_at": result["created_at"],
            "updated_at": result["updated_at"],
        }

    def _format_prompt(
        self,
        template: str,
        inputs: Optional[dict[str, Any]],
        input_types: dict[str, str],
    ) -> str:
        if inputs:
            # optional input validation if needed
            for k, _v in inputs.items():
                if k not in input_types:
                    raise ValueError(
                        f"Unexpected input '{k}' for prompt with input types {input_types}"
                    )
            return template.format(**inputs)
        return template

    async def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        """Public method to update a prompt with proper cache invalidation."""
        # First invalidate all caches for this prompt
        self._template_cache.invalidate(name)
        cache_keys_to_invalidate = [
            key
            for key in self._prompt_cache._cache.keys()
            if key.startswith(f"{name}:") or key == name
        ]
        for key in cache_keys_to_invalidate:
            self._prompt_cache.invalidate(key)

        # Perform the update
        await self._update_prompt_impl(name, template, input_types)

        # Force refresh template cache
        template_info = await self._get_template_info(name)
        if template_info:
            self._template_cache.set(name, template_info)

    @abstractmethod
    async def _update_prompt_impl(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        """Implementation of prompt update logic."""
        pass

    @abstractmethod
    async def _get_template_info(self, prompt_name: str) -> Optional[dict]:
        """Get template info with caching."""
        pass

    @abstractmethod
    async def _get_prompt_impl(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        bypass_template_cache: bool = False,
    ) -> str:
        """Implementation of prompt retrieval logic."""
        pass


class PostgresPromptsHandler(CacheablePromptHandler):
    """PostgreSQL implementation of the CacheablePromptHandler."""

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        prompt_directory: Optional[Path] = None,
        **cache_options,
    ):
        super().__init__(**cache_options)
        self.prompt_directory = (
            prompt_directory or Path(os.path.dirname(__file__)) / "prompts"
        )
        self.connection_manager = connection_manager
        self.project_name = project_name
        self.prompts: dict[str, dict[str, str | dict[str, str]]] = {}

    async def _load_prompts(self) -> None:
        """Load prompts from both database and YAML files."""
        # First load from database
        await self._load_prompts_from_database()

        # Then load from YAML files, potentially overriding unmodified database entries
        await self._load_prompts_from_yaml_directory()

    async def _load_prompts_from_database(self) -> None:
        """Load prompts from the database."""
        query = f"""
        SELECT id, name, template, input_types, created_at, updated_at
        FROM {self._get_table_name("prompts")};
        """
        try:
            results = await self.connection_manager.fetch_query(query)
            for row in results:
                logger.info(f"Loading saved prompt: {row['name']}")

                # Ensure input_types is a dictionary
                input_types = row["input_types"]
                if isinstance(input_types, str):
                    input_types = json.loads(input_types)

                self.prompts[row["name"]] = {
                    "id": row["id"],
                    "template": row["template"],
                    "input_types": input_types,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                # Pre-populate the template cache
                self._template_cache.set(
                    row["name"],
                    {
                        "id": row["id"],
                        "template": row["template"],
                        "input_types": input_types,
                    },
                )
            logger.debug(f"Loaded {len(results)} prompts from database")
        except Exception as e:
            logger.error(f"Failed to load prompts from database: {e}")
            raise

    async def _load_prompts_from_yaml_directory(
        self, default_overwrite_on_diff: bool = False
    ) -> None:
        """Load prompts from YAML files in the specified directory.

        :param default_overwrite_on_diff: If a YAML prompt does not specify
            'overwrite_on_diff', we use this default.
        """
        if not self.prompt_directory.is_dir():
            logger.warning(
                f"Prompt directory not found: {self.prompt_directory}"
            )
            return

        logger.info(f"Loading prompts from {self.prompt_directory}")
        for yaml_file in self.prompt_directory.glob("*.yaml"):
            logger.debug(f"Processing {yaml_file}")
            try:
                with open(yaml_file, "r", encoding="utf-8") as file:
                    data = yaml.safe_load(file)
                    if not isinstance(data, dict):
                        raise ValueError(
                            f"Invalid format in YAML file {yaml_file}"
                        )

                    for name, prompt_data in data.items():
                        # Attempt to parse the relevant prompt fields
                        template = prompt_data.get("template")
                        input_types = prompt_data.get("input_types", {})

                        # Decide on per-prompt overwrite behavior (or fallback)
                        overwrite_on_diff = prompt_data.get(
                            "overwrite_on_diff", default_overwrite_on_diff
                        )
                        # Some logic to determine if we *should* modify
                        # For instance, preserve only if it has never been updated
                        # (i.e., created_at == updated_at).
                        should_modify = True
                        if name in self.prompts:
                            existing = self.prompts[name]
                            should_modify = (
                                existing["created_at"]
                                == existing["updated_at"]
                            )

                        # If should_modify is True, the default logic is
                        #   preserve_existing = False,
                        # so we can pass that in. Otherwise, preserve_existing=True
                        # effectively means we skip the update.
                        logger.info(
                            f"Loading default prompt: {name} from {yaml_file}."
                        )

                        await self.add_prompt(
                            name=name,
                            template=template,
                            input_types=input_types,
                            preserve_existing=False,
                            overwrite_on_diff=overwrite_on_diff,
                        )
            except Exception as e:
                logger.error(f"Error loading {yaml_file}: {e}")
                continue

    def _get_table_name(self, base_name: str) -> str:
        """Get the fully qualified table name."""
        return f"{self.project_name}.{base_name}"

    # Implementation of abstract methods from CacheablePromptHandler
    async def _get_prompt_impl(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        bypass_template_cache: bool = False,
    ) -> str:
        """Implementation of database prompt retrieval."""
        # If we're bypassing the template cache, skip the cache lookup
        if not bypass_template_cache:
            template_info = self._template_cache.get(prompt_name)
            if template_info is not None:
                logger.debug(f"Template cache hit: {prompt_name}")
                # use that
                return self._format_prompt(
                    template_info["template"],
                    inputs,
                    template_info["input_types"],
                )

        # If we get here, either no cache was found or bypass_cache is True
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
        if isinstance(input_types, str):
            input_types = json.loads(input_types)

        # Update template cache if not bypassing it
        if not bypass_template_cache:
            self._template_cache.set(
                prompt_name, {"template": template, "input_types": input_types}
            )

        return self._format_prompt(template, inputs, input_types)

    async def _get_template_info(self, prompt_name: str) -> Optional[dict]:  # type: ignore
        """Get template info with caching."""
        cached = self._template_cache.get(prompt_name)
        if cached is not None:
            return cached

        query = f"""
        SELECT template, input_types
        FROM {self._get_table_name("prompts")}
        WHERE name = $1;
        """

        result = await self.connection_manager.fetchrow_query(
            query, [prompt_name]
        )

        if result:
            # Ensure input_types is a dictionary
            input_types = result["input_types"]
            if isinstance(input_types, str):
                input_types = json.loads(input_types)

            template_info = {
                "template": result["template"],
                "input_types": input_types,
            }
            self._template_cache.set(prompt_name, template_info)
            return template_info

        return None

    async def _update_prompt_impl(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        """Implementation of database prompt update with proper connection
        handling."""
        if not template and not input_types:
            return

        # Clear caches first
        self._template_cache.invalidate(name)
        for key in list(self._prompt_cache._cache.keys()):
            if key.startswith(f"{name}:"):
                self._prompt_cache.invalidate(key)

        # Build update query
        set_clauses = []
        params = [name]  # First parameter is always the name
        param_index = 2  # Start from 2 since $1 is name

        if template:
            set_clauses.append(f"template = ${param_index}")
            params.append(template)
            param_index += 1

        if input_types:
            set_clauses.append(f"input_types = ${param_index}")
            params.append(json.dumps(input_types))
            param_index += 1

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        query = f"""
        UPDATE {self._get_table_name("prompts")}
        SET {", ".join(set_clauses)}
        WHERE name = $1
        RETURNING id, template, input_types;
        """

        try:
            # Execute update and get returned values
            result = await self.connection_manager.fetchrow_query(
                query, params
            )

            if not result:
                raise ValueError(f"Prompt template '{name}' not found")

            # Update in-memory state
            if name in self.prompts:
                if template:
                    self.prompts[name]["template"] = template
                if input_types:
                    self.prompts[name]["input_types"] = input_types
                self.prompts[name]["updated_at"] = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Failed to update prompt {name}: {str(e)}")
            raise

    async def create_tables(self):
        """Create the necessary tables for storing prompts."""
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name("prompts")} (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
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
        await self._load_prompts()

    async def add_prompt(
        self,
        name: str,
        template: str,
        input_types: dict[str, str],
        preserve_existing: bool = False,
        overwrite_on_diff: bool = False,  # <-- new param
    ) -> None:
        """Add or update a prompt.

        If `preserve_existing` is True and prompt already exists, we skip updating.

        If `overwrite_on_diff` is True and an existing prompt differs from what is provided,
        we overwrite and log a warning. Otherwise, we skip if the prompt differs.
        """
        # Check if prompt is in-memory
        existing_prompt = self.prompts.get(name)

        # If preserving existing and it already exists, skip entirely
        if preserve_existing and existing_prompt:
            logger.debug(
                f"Preserving existing prompt: {name}, skipping update."
            )
            return

        # If an existing prompt is found, check for diffs
        if existing_prompt:
            existing_template = existing_prompt["template"]
            existing_input_types = existing_prompt["input_types"]

            # If there's a difference in template or input_types, decide to overwrite or skip
            if (
                existing_template != template
                or existing_input_types != input_types
            ):
                if overwrite_on_diff:
                    logger.warning(
                        f"Overwriting existing prompt '{name}' due to detected diff."
                    )
                else:
                    logger.info(
                        f"Prompt '{name}' differs from existing but overwrite_on_diff=False. Skipping update."
                    )
                    return

        prompt_id = generate_default_prompt_id(name)

        # Ensure input_types is properly serialized
        input_types_json = (
            json.dumps(input_types)
            if isinstance(input_types, dict)
            else input_types
        )

        # Upsert logic
        query = f"""
        INSERT INTO {self._get_table_name("prompts")} (id, name, template, input_types)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (name) DO UPDATE
        SET template = EXCLUDED.template,
            input_types = EXCLUDED.input_types,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id, created_at, updated_at;
        """

        result = await self.connection_manager.fetchrow_query(
            query, [prompt_id, name, template, input_types_json]
        )

        self.prompts[name] = {
            "id": result["id"],
            "template": template,
            "input_types": input_types,
            "created_at": result["created_at"],
            "updated_at": result["updated_at"],
        }

        # Update template cache
        self._template_cache.set(
            name,
            {
                "id": prompt_id,
                "template": template,
                "input_types": input_types,
            },
        )

        # Invalidate any cached formatted prompts
        for key in list(self._prompt_cache._cache.keys()):
            if key.startswith(f"{name}:"):
                self._prompt_cache.invalidate(key)

    async def get_all_prompts(self) -> dict[str, Any]:
        """Retrieve all stored prompts."""
        query = f"""
        SELECT id, name, template, input_types, created_at, updated_at, COUNT(*) OVER() AS total_entries
        FROM {self._get_table_name("prompts")};
        """
        results = await self.connection_manager.fetch_query(query)

        if not results:
            return {"results": [], "total_entries": 0}

        total_entries = results[0]["total_entries"] if results else 0

        prompts = [
            {
                "name": row["name"],
                "id": row["id"],
                "template": row["template"],
                "input_types": (
                    json.loads(row["input_types"])
                    if isinstance(row["input_types"], str)
                    else row["input_types"]
                ),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in results
        ]

        return {"results": prompts, "total_entries": total_entries}

    async def delete_prompt(self, name: str) -> None:
        """Delete a prompt template."""
        query = f"""
        DELETE FROM {self._get_table_name("prompts")}
        WHERE name = $1;
        """
        result = await self.connection_manager.execute_query(query, [name])
        if result == "DELETE 0":
            raise ValueError(f"Prompt template '{name}' not found")

        # Invalidate caches
        self._template_cache.invalidate(name)
        for key in list(self._prompt_cache._cache.keys()):
            if key.startswith(f"{name}:"):
                self._prompt_cache.invalidate(key)

    async def get_message_payload(
        self,
        system_prompt_name: Optional[str] = None,
        system_role: str = "system",
        system_inputs: dict | None = None,
        system_prompt_override: Optional[str] = None,
        task_prompt_name: Optional[str] = None,
        task_role: str = "user",
        task_inputs: Optional[dict] = None,
        task_prompt: Optional[str] = None,
    ) -> list[dict]:
        """Create a message payload from system and task prompts."""
        if system_inputs is None:
            system_inputs = {}
        if task_inputs is None:
            task_inputs = {}
        if system_prompt_override:
            system_prompt = system_prompt_override
        else:
            system_prompt = await self.get_cached_prompt(
                system_prompt_name or "system",
                system_inputs,
                prompt_override=system_prompt_override,
            )

        task_prompt = await self.get_cached_prompt(
            task_prompt_name or "rag",
            task_inputs,
            prompt_override=task_prompt,
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
