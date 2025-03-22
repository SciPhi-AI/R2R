import glob
import json
import logging
import os
from typing import Dict, List, Optional, Union, Any

import yaml

from datetime import datetime


class PostgresPromptsHandler:
    """Simple prompt handling system with PostgreSQL persistence and caching."""
    
    def __init__(self, project_name, connection_manager, prompt_directory=None):
        self.project_name = project_name
        self.connection_manager = connection_manager
        self.prompt_directory = prompt_directory
        self.prompts = {}  # Single in-memory store
        self.cache = {}    # Single cache for formatted results
        self.logger = logging.getLogger(__name__)
        
    async def create_tables(self):
        """Create necessary database tables if they don't exist."""
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("prompts")} (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                template TEXT NOT NULL,
                input_types JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """
        await self.connection_manager.execute_query(query)
        
        # Load prompts from database
        await self._load_prompts()
        
        # Load prompts from YAML files if directory provided
        if self.prompt_directory:
            await self._load_prompts_from_yaml_directory(self.prompt_directory)
    
    async def _load_prompts(self):
        """Load all prompts from the database."""
        query = f"""
            SELECT id, name, template, input_types, created_at, updated_at 
            FROM {self._get_table_name("prompts")}
        """
        rows = await self.connection_manager.fetch_query(query)
        
        for row in rows:
            self.prompts[row["name"]] = {
                "template": row["template"],
                "input_types": row["input_types"],
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        
        return self.prompts
    
    async def _load_prompts_from_yaml_directory(self, directory):
        """Load prompts from YAML files in the specified directory."""
        yaml_files = glob.glob(os.path.join(directory, "*.yaml"))
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r") as f:
                    yaml_data = yaml.safe_load(f)
                
                if not yaml_data or "prompts" not in yaml_data:
                    self.logger.warning(f"No prompts found in {yaml_file}")
                    continue
                
                for prompt_data in yaml_data["prompts"]:
                    name = prompt_data.get("name")
                    template = prompt_data.get("template")
                    input_types = prompt_data.get("input_types", {})
                    preserve_existing = prompt_data.get("preserve_existing", False)
                    
                    if not name or not template:
                        self.logger.warning(f"Invalid prompt data in {yaml_file}: {prompt_data}")
                        continue
                    
                    await self.add_prompt(
                        name=name,
                        template=template,
                        input_types=input_types,
                        preserve_existing=preserve_existing
                    )
            except Exception as e:
                self.logger.error(f"Error loading prompts from {yaml_file}: {e}")
    
    def _get_table_name(self, table):
        """Get the fully qualified table name."""
        return f"{self.project_name}.{table}"
    
    async def get_all_prompts(self):
        """Get all prompts."""
        return self.prompts
    
    async def get_prompt(self, name):
        """Get a prompt by name."""
        if name not in self.prompts:
            raise ValueError(f"Prompt template '{name}' not found")
        return self.prompts[name]
    
    async def add_prompt(self, name, template, input_types, preserve_existing=False):
        """Add or update a prompt."""
        # Check if prompt already exists and should be preserved
        if name in self.prompts and preserve_existing:
            self.logger.info(f"Prompt '{name}' already exists and preserve_existing=True, skipping update")
            return
        
        # Add or update the prompt in the database
        query = f"""
            INSERT INTO {self._get_table_name("prompts")} (name, template, input_types)
            VALUES ($1, $2, $3)
            ON CONFLICT (name) 
            DO UPDATE SET template = $2, input_types = $3, updated_at = NOW()
            RETURNING id, name, template, input_types, created_at, updated_at
        """
        result = await self.connection_manager.fetchrow_query(
            query, [name, template, input_types]
        )
        
        # Update in-memory dictionary
        self.prompts[name] = {
            "template": template,
            "input_types": input_types,
            "id": result["id"],
            "created_at": result["created_at"],
            "updated_at": result["updated_at"]
        }
        
        # Clear cache for this prompt
        self._clear_cache_for_prompt(name)
    
    async def update_prompt(self, name, template=None, input_types=None):
        """Update an existing prompt."""
        if name not in self.prompts:
            raise ValueError(f"Prompt template '{name}' not found")
        
        current = self.prompts[name]
        new_template = template if template is not None else current["template"]
        new_input_types = input_types if input_types is not None else current["input_types"]
        
        # Build the query based on what needs to be updated
        if template is not None and input_types is not None:
            query = f"""
                UPDATE {self._get_table_name("prompts")}
                SET template = $1, input_types = $2, updated_at = NOW()
                WHERE name = $3
                RETURNING id, name, template, input_types, created_at, updated_at
            """
            params = [new_template, new_input_types, name]
        elif template is not None:
            query = f"""
                UPDATE {self._get_table_name("prompts")}
                SET template = $1, updated_at = NOW()
                WHERE name = $2
                RETURNING id, name, template, input_types, created_at, updated_at
            """
            params = [new_template, name]
        elif input_types is not None:
            query = f"""
                UPDATE {self._get_table_name("prompts")}
                SET input_types = $1, updated_at = NOW()
                WHERE name = $2
                RETURNING id, name, template, input_types, created_at, updated_at
            """
            params = [new_input_types, name]
        else:
            return  # Nothing to update
        
        # Execute the update
        result = await self.connection_manager.fetchrow_query(query, params)
        
        # Update in-memory dictionary
        self.prompts[name] = {
            "template": new_template,
            "input_types": new_input_types,
            "id": result["id"],
            "created_at": result["created_at"],
            "updated_at": result["updated_at"]
        }
        
        # Clear cache for this prompt
        self._clear_cache_for_prompt(name)
    
    async def delete_prompt(self, name):
        """Delete a prompt."""
        if name not in self.prompts:
            raise ValueError(f"Prompt template '{name}' not found")
        
        # Delete from database
        query = f"DELETE FROM {self._get_table_name('prompts')} WHERE name = $1"
        await self.connection_manager.execute_query(query, [name])
        
        # Remove from in-memory dictionary
        del self.prompts[name]
        
        # Clear cache for this prompt
        self._clear_cache_for_prompt(name)
    
    def _cache_key(self, prompt_name, inputs):
        """Generate a cache key for the prompt with inputs."""
        if not inputs:
            return prompt_name
        
        # Sort inputs to ensure consistent keys
        sorted_inputs = json.dumps(inputs, sort_keys=True)
        return f"{prompt_name}:{sorted_inputs}"
    
    def _clear_cache_for_prompt(self, name):
        """Clear all cached entries for a specific prompt."""
        prefix = f"{name}:"
        self.cache = {k: v for k, v in self.cache.items() 
                     if not (k == name or k.startswith(prefix))}
    
    async def get_cached_prompt(self, prompt_name, inputs=None, bypass_cache=False):
        """Get a formatted prompt, using cache if available."""
        if inputs is None:
            inputs = {}
        
        # Generate cache key
        cache_key = self._cache_key(prompt_name, inputs)
        
        # Return from cache if available and not bypassing
        if not bypass_cache and cache_key in self.cache:
            return self.cache[cache_key]
        
        # Get prompt data
        if prompt_name not in self.prompts:
            raise ValueError(f"Prompt template '{prompt_name}' not found")
        
        prompt_data = self.prompts[prompt_name]
        template = prompt_data["template"]
        expected_input_types = prompt_data["input_types"]
        
        # Validate input types (optional)
        for key, type_name in expected_input_types.items():
            if key not in inputs:
                raise ValueError(f"Missing required input '{key}' for prompt '{prompt_name}'")
        
        # Format the template
        try:
            formatted = template.format(**inputs)
        except KeyError as e:
            raise ValueError(f"Missing input in format string: {e}")
        except Exception as e:
            raise ValueError(f"Error formatting prompt '{prompt_name}': {e}")
        
        # Cache the result
        self.cache[cache_key] = formatted
        
        return formatted
