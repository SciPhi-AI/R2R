import json
import logging
import os
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar

import yaml

from core.base import PromptHandler, generate_default_prompt_id

from .base import PostgresConnectionManager

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Represents a cached item with metadata"""

    value: T
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0


class Cache(Generic[T]):
    """A generic cache implementation with TTL and LRU-like features"""

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
        """Retrieve an item from cache"""
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
        """Store an item in cache"""
        self._maybe_cleanup()

        now = datetime.now()
        self._cache[key] = CacheEntry(
            value=value, created_at=now, last_accessed=now
        )

        if self._max_size and len(self._cache) > self._max_size:
            self._evict_lru()

    def invalidate(self, key: str) -> None:
        """Remove an item from cache"""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached items"""
        self._cache.clear()

    def _maybe_cleanup(self) -> None:
        """Periodically clean up expired entries"""
        now = datetime.now()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup()
            self._last_cleanup = now

    def _cleanup(self) -> None:
        """Remove expired entries"""
        if not self._ttl:
            return

        now = datetime.now()
        expired = [
            k for k, v in self._cache.items() if now - v.created_at > self._ttl
        ]
        for k in expired:
            del self._cache[k]

    def _evict_lru(self) -> None:
        """Remove least recently used item"""
        if not self._cache:
            return

        lru_key = min(
            self._cache.keys(), key=lambda k: self._cache[k].last_accessed
        )
        del self._cache[lru_key]


class CacheablePromptHandler(PromptHandler):
    """Abstract base class that adds caching capabilities to prompt handlers"""

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
        """Generate a cache key for a prompt request"""
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
        """Get a prompt with caching support"""
        if prompt_override:
            if inputs:
                try:
                    return prompt_override.format(**inputs)
                except KeyError:
                    return prompt_override
            return prompt_override

        cache_key = self._cache_key(prompt_name, inputs)

        if not bypass_cache:
            cached = self._prompt_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for prompt: {cache_key}")
                return cached

        result = await self._get_prompt_impl(prompt_name, inputs)
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

    @abstractmethod
    async def _get_prompt_impl(
        self, prompt_name: str, inputs: Optional[dict[str, Any]] = None
    ) -> str:
        """Implementation of prompt retrieval logic"""
        pass

    async def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> None:
        """Public method to update a prompt with proper cache invalidation"""
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
        """Implementation of prompt update logic"""
        pass

    @abstractmethod
    async def _get_template_info(self, prompt_name: str) -> Optional[dict]:
        """Get template info with caching"""
        pass


class PostgresPromptHandler(CacheablePromptHandler):
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

    async def _load_prompts_from_yaml_directory(self) -> None:
        """Load prompts from YAML files in the specified directory."""
        if not self.prompt_directory.is_dir():
            logger.warning(
                f"Prompt directory not found: {self.prompt_directory}"
            )
            return

        logger.info(f"Loading prompts from {self.prompt_directory}")
        for yaml_file in self.prompt_directory.glob("*.yaml"):
            logger.debug(f"Processing {yaml_file}")
            try:
                with open(yaml_file, "r") as file:
                    data = yaml.safe_load(file)
                    if not isinstance(data, dict):
                        raise ValueError(
                            f"Invalid format in YAML file {yaml_file}"
                        )

                    for name, prompt_data in data.items():
                        should_modify = True
                        if name in self.prompts:
                            # Only modify if the prompt hasn't been updated since creation
                            existing = self.prompts[name]
                            should_modify = (
                                existing["created_at"]
                                == existing["updated_at"]
                            )

                        if should_modify:
                            logger.info(f"Loading default prompt: {name}")
                            await self.add_prompt(
                                name=name,
                                template=prompt_data["template"],
                                input_types=prompt_data.get("input_types", {}),
                                preserve_existing=(not should_modify),
                            )
            except Exception as e:
                logger.error(f"Error loading {yaml_file}: {e}")
                continue

    def _get_table_name(self, base_name: str) -> str:
        """Get the fully qualified table name."""
        return f"{self.project_name}.{base_name}"

    # Implementation of abstract methods from CacheablePromptHandler
    async def _get_prompt_impl(
        self, prompt_name: str, inputs: Optional[dict[str, Any]] = None
    ) -> str:
        """Implementation of database prompt retrieval"""
        template_info = await self._get_template_info(prompt_name)

        if not template_info:
            raise ValueError(f"Prompt template '{prompt_name}' not found")

        template, input_types = (
            template_info["template"],
            template_info["input_types"],
        )

        if inputs:
            # Validate input types
            for key, value in inputs.items():
                expected_type = input_types.get(key)
                if not expected_type:
                    raise ValueError(f"Unexpected input key: {key}")
            return template.format(**inputs)

        return template

    async def _get_template_info(self, prompt_name: str) -> Optional[dict]:  # type: ignore
        """Get template info with caching"""
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
        """Implementation of database prompt update with proper connection handling"""
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
        SET {', '.join(set_clauses)}
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
    ) -> None:
        """Add or update a prompt."""
        if preserve_existing and name in self.prompts:
            return

        id = generate_default_prompt_id(name)

        # Ensure input_types is properly serialized
        input_types_json = (
            json.dumps(input_types)
            if isinstance(input_types, dict)
            else input_types
        )

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
            query, [id, name, template, input_types_json]
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
                "id": id,
                "template": template,
                "input_types": input_types,
            },  # Store as dict in cache
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
            system_prompt = await self.get_cached_prompt(
                system_prompt_name or "default_system",
                system_inputs,
                prompt_override=system_prompt_override,
            )

        task_prompt = await self.get_cached_prompt(
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
