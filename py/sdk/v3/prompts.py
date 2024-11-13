import json
from inspect import isasyncgenfunction, iscoroutinefunction
from typing import Optional

from ..base.base_client import sync_generator_wrapper, sync_wrapper


class PromptsSDK:
    """
    SDK for interacting with prompts in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self, name: str, template: str, input_types: dict
    ) -> dict:
        """
        Create a new prompt.
        Args:
            name (str): The name of the prompt
            template (str): The template string for the prompt
            input_types (dict): A dictionary mapping input names to their types
        Returns:
            dict: Created prompt information
        """
        data = {"name": name, "template": template, "input_types": input_types}
        return await self.client._make_request("POST", "prompts", json=data)

    async def list(self) -> dict:
        """
        List all available prompts.
        Returns:
            dict: List of all available prompts
        """
        return await self.client._make_request("GET", "prompts")

    async def retrieve(
        self,
        name: str,
        inputs: Optional[dict] = None,
        prompt_override: Optional[str] = None,
    ) -> dict:
        """
        Get a specific prompt by name, optionally with inputs and override.
        Args:
            name (str): The name of the prompt to retrieve
            inputs (Optional[dict]): JSON-encoded inputs for the prompt
            prompt_override (Optional[str]): An override for the prompt template
        Returns:
            dict: The requested prompt with applied inputs and/or override
        """
        params = {}
        if inputs:
            params["inputs"] = json.dumps(inputs)
        if prompt_override:
            params["prompt_override"] = prompt_override
        return await self.client._make_request(
            "POST", f"prompts/{name}", params=params
        )

    async def update(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict] = None,
    ) -> dict:
        """
        Update an existing prompt's template and/or input types.
        Args:
            name (str): The name of the prompt to update
            template (Optional[str]): The updated template string for the prompt
            input_types (Optional[dict]): The updated dictionary mapping input names to their types
        Returns:
            dict: The updated prompt details
        """
        data: dict = {}
        if template:
            data["template"] = template
        if input_types:
            data["input_types"] = json.dumps(input_types)
        return await self.client._make_request(
            "PUT", f"prompts/{name}", json=data
        )

    async def delete(self, name: str) -> bool:
        """
        Delete a prompt by name.
        Args:
            name (str): The name of the prompt to delete
        Returns:
            bool: True if deletion was successful
        """
        result = await self.client._make_request("DELETE", f"prompts/{name}")
        return result.get("results", True)


class SyncPromptsSDK:
    """Synchronous wrapper for PromptsSDK"""

    def __init__(self, async_sdk: PromptsSDK):
        self._async_sdk = async_sdk

        # Get all attributes from the instance
        for name in dir(async_sdk):
            if not name.startswith("_"):  # Skip private methods
                attr = getattr(async_sdk, name)
                # Check if it's a method and if it's async
                if callable(attr) and (
                    iscoroutinefunction(attr) or isasyncgenfunction(attr)
                ):
                    if isasyncgenfunction(attr):
                        setattr(self, name, sync_generator_wrapper(attr))
                    else:
                        setattr(self, name, sync_wrapper(attr))
