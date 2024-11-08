import textwrap
from typing import Optional, Union

from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel, Field, Json

from core.base import R2RException, RunType
from core.base.api.models import (
    ResultsWrapper,
    WrappedGetPromptsResponse,
    WrappedPromptMessageResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from .base_router import BaseRouterV3


class PromptConfig(BaseModel):
    name: str = Field(..., description="The name of the prompt")
    template: str = Field(
        ..., description="The template string for the prompt"
    )
    input_types: dict[str, str] = Field(
        default={},
        description="A dictionary mapping input names to their types",
    )


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
        @self.router.post(
            "/prompts",
            summary="Create a new prompt",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.prompts.create(
                                name="greeting_prompt",
                                template="Hello, {name}!",
                                input_types={"name": "string"}
                            )
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/prompts" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json" \\
                                -d '{"name": "greeting_prompt", "template": "Hello, {name}!", "input_types": {"name": "string"}}'
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_prompt(
            config: PromptConfig = Body(
                ..., description="The configuration for the new prompt"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedPromptMessageResponse:
            """
            Create a new prompt with the given configuration.

            This endpoint allows superusers to create a new prompt with a specified name, template, and input types.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can create prompts.",
                    403,
                )
            result = await self.services["management"].add_prompt(
                config.name, config.template, config.input_types
            )
            return result

        @self.router.get(
            "/prompts",
            summary="List all prompts",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.prompts.list()
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                                curl -X GET "https://api.example.com/v3/prompts" \\
                                    -H "Authorization: Bearer YOUR_API_KEY"
                                """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_prompts(
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGetPromptsResponse:
            """
            List all available prompts.

            This endpoint retrieves a list of all prompts in the system. Only superusers can access this endpoint.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can list prompts.",
                    403,
                )
            result = await self.services["management"].get_all_prompts()
            return {"prompts": result}  # type: ignore

        @self.router.get(
            "/prompts/{name}",
            summary="Get a specific prompt",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.prompts.get(
                                "greeting_prompt",
                                inputs={"name": "John"},
                                prompt_override="Hi, {name}!"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/prompts/greeting_prompt?inputs=%7B%22name%22%3A%22John%22%7D&prompt_override=Hi%2C%20%7Bname%7D!" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
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

            This endpoint retrieves a specific prompt and allows for optional inputs and template override.
            Only superusers can access this endpoint.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can retrieve prompts.",
                    403,
                )
            result = await self.services["management"].get_prompt(
                name, inputs, prompt_override
            )
            return result  # type: ignore

        @self.router.put(
            "/prompts/{name}",
            summary="Update an existing prompt",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.prompts.update(
                                "greeting_prompt",
                                template="Greetings, {name}!",
                                input_types={"name": "string", "age": "integer"}
                            )
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X PUT "https://api.example.com/v3/prompts/greeting_prompt" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json" \\
                                -d '{"template": "Greetings, {name}!", "input_types": {"name": "string", "age": "integer"}}'
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_prompt(
            name: str = Path(..., description="Prompt name"),
            template: Optional[str] = Body(
                None, description="Updated prompt template"
            ),
            input_types: Optional[Json[dict[str, str]]] = Body(
                {}, description="Updated input types"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedPromptMessageResponse:
            """
            Update an existing prompt's template and/or input types.

            This endpoint allows superusers to update the template and input types of an existing prompt.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can update prompts.",
                    403,
                )
            result = await self.services["management"].update_prompt(
                name, template, input_types
            )
            return result  # type: ignore

        @self.router.delete(
            "/prompts/{name}",
            summary="Delete a prompt",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.prompts.delete("greeting_prompt")
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/prompts/greeting_prompt" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_prompt(
            name: str = Path(..., description="Prompt name"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[bool]:
            """
            Delete a prompt by name.

            This endpoint allows superusers to delete an existing prompt.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can delete prompts.",
                    403,
                )
            await self.services["management"].delete_prompt(name)
            return True  # type: ignore
