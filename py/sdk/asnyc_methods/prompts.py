import json
from typing import Any, Optional

from shared.api.models import (
    WrappedBooleanResponse,
    WrappedGenericMessageResponse,
    WrappedPromptResponse,
    WrappedPromptsResponse,
)


class PromptsSDK:
    def __init__(self, client):
        self.client = client

    async def create(
        self, name: str, template: str, input_types: dict
    ) -> WrappedGenericMessageResponse:
        """Create a new prompt.

        Args:
            name (str): The name of the prompt
            template (str): The template string for the prompt
            input_types (dict): A dictionary mapping input names to their types
        Returns:
            dict: Created prompt information
        """
        data: dict[str, Any] = {
            "name": name,
            "template": template,
            "input_types": input_types,
        }
        response_dict = await self.client._make_request(
            "POST",
            "prompts",
            json=data,
            version="v3",
        )

        return WrappedGenericMessageResponse(**response_dict)

    async def list(self) -> WrappedPromptsResponse:
        """List all available prompts.

        Returns:
            dict: List of all available prompts
        """
        response_dict = await self.client._make_request(
            "GET",
            "prompts",
            version="v3",
        )

        return WrappedPromptsResponse(**response_dict)

    async def retrieve(
        self,
        name: str,
        inputs: Optional[dict] = None,
        prompt_override: Optional[str] = None,
    ) -> WrappedPromptResponse:
        """Get a specific prompt by name, optionally with inputs and override.

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
        response_dict = await self.client._make_request(
            "POST",
            f"prompts/{name}",
            params=params,
            version="v3",
        )

        return WrappedPromptResponse(**response_dict)

    async def update(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict] = None,
    ) -> WrappedGenericMessageResponse:
        """Update an existing prompt's template and/or input types.

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
        response_dict = await self.client._make_request(
            "PUT",
            f"prompts/{name}",
            json=data,
            version="v3",
        )

        return WrappedGenericMessageResponse(**response_dict)

    async def delete(self, name: str) -> WrappedBooleanResponse:
        """Delete a prompt by name.

        Args:
            name (str): The name of the prompt to delete
        Returns:
            bool: True if deletion was successful
        """
        response_dict = await self.client._make_request(
            "DELETE",
            f"prompts/{name}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)
