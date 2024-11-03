from typing import List, Optional, Union
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel, Json

from core.base import R2RException, RunType
from core.base.api.models import (
    WrappedDeleteResponse,
    WrappedGetPromptsResponse,
    WrappedPromptMessageResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from .base_router import BaseRouterV3


class PromptConfig(BaseModel):
    name: str
    template: str
    input_types: dict[str, str] = {}


class PromptsRouter(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: Union[
            HatchetOrchestrationProvider, SimpleOrchestrationProvider
        ],
        run_type: RunType = RunType.MANAGEMENT,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _setup_routes(self):
        @self.router.post("/prompts")
        @self.base_endpoint
        async def create_prompt(
            config: PromptConfig = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedPromptMessageResponse:
            """
            Create a new prompt with the given configuration.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can create prompts.",
                    403,
                )

            result = await self.services.add_prompt(
                config.name, config.template, config.input_types
            )
            return result

        @self.router.get("/prompts")
        @self.base_endpoint
        async def list_prompts(
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGetPromptsResponse:
            """
            List all available prompts.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can list prompts.",
                    403,
                )

            result = await self.services.get_all_prompts()
            return {"prompts": result}

        @self.router.get("/prompts/{name}")
        @self.base_endpoint
        async def get_prompt(
            name: str = Path(..., description="Prompt name"),
            inputs: Optional[Json[dict]] = Query(
                None, description="JSON-encoded prompt inputs"
            ),
            prompt_override: Optional[str] = Query(
                None, description="Prompt override"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedPromptMessageResponse:
            """
            Get a specific prompt by name, optionally with inputs and override.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can retrieve prompts.",
                    403,
                )

            result = await self.services.get_prompt(
                name, inputs, prompt_override
            )
            return result

        @self.router.put("/prompts/{name}")
        @self.base_endpoint
        async def update_prompt(
            name: str = Path(..., description="Prompt name"),
            template: Optional[str] = Body(
                None, description="Updated prompt template"
            ),
            input_types: Optional[dict[str, str]] = Body(
                {}, description="Updated input types"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedPromptMessageResponse:
            """
            Update an existing prompt's template and/or input types.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can update prompts.",
                    403,
                )

            result = await self.services.update_prompt(
                name, template, input_types
            )
            return result

        @self.router.delete("/prompts/{name}")
        @self.base_endpoint
        async def delete_prompt(
            name: str = Path(..., description="Prompt name"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedDeleteResponse:
            """
            Delete a prompt by name.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can delete prompts.",
                    403,
                )

            await self.services.delete_prompt(name)
            return None
