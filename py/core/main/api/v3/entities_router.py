import logging
import textwrap
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query

from core.base import R2RException, RunType
from core.base.abstractions import DataLevel

from core.base.api.models import (
    GenericBooleanResponse,
    WrappedBooleanResponse,
    WrappedEntityResponse,
    WrappedEntitiesResponse,
)


from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from .base_router import BaseRouterV3

from fastapi import Request

logger = logging.getLogger()


class EntitiesRouter(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: (
            HatchetOrchestrationProvider | SimpleOrchestrationProvider
        ),
        run_type: RunType = RunType.KG,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _get_path_level(self, request: Request) -> DataLevel:
        path = request.url.path
        if "/chunks/" in path:
            return DataLevel.CHUNK
        elif "/documents/" in path:
            return DataLevel.DOCUMENT
        else:
            return DataLevel.GRAPH

    def _setup_routes(self):

        @self.router.post(
            "/entities",
            summary="Create a new entity",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.entities.create(
                                name="entity1",
                                description="description1",
                                attributes={"attr1": "value1"},
                                category="category1",
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.entities.create({
                                    name: "entity1",
                                    description: "description1",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def create_entity(
            name: str = Body(..., description="The name of the entity"),
            description: str = Body(
                ..., description="The description of the entity"
            ),
            attributes: Optional[dict] = Body(
                None,
                description="The attributes of the entity",
            ),
            category: Optional[str] = Body(
                None,
                description="The category of the entity",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedEntityResponse:
            """
            Creates a new entity in the database.
            """

            return await self.services["kg"].create_entities(
                name=name,
                description=description,
                category=category,
                attributes=attributes,
                user_id=auth_user.id,
            )

        @self.router.get(
            "/entities",
            summary="List entities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.entities.list()
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.entities.list({});
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def list_entities(
            ids: list[str] = Query(
                [],
                description="A list of entity IDs to retrieve. If not provided, all entities will be returned.",
            ),
            offset: int = Query(
                0,
                ge=0,
                description="Specifies the number of objects to skip. Defaults to 0.",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedEntitiesResponse:
            """
            Returns a paginated list of entities the authenticated user has access to.

            Results can be filtered by providing specific entity IDs. Regular users will only see
            entities they have access to. Superusers can see all entities.

            The entities are returned in order of last modification, with most recent first.
            """

            requesting_user_id = (
                None if auth_user.is_superuser else [auth_user.id]
            )

            entity_uuids = [UUID(entity_id) for entity_id in ids]

            list_entities_response = await self.services["kg"].list_entities(
                user_ids=requesting_user_id,
                entity_ids=entity_uuids,
                offset=offset,
                limit=limit,
            )

            return (  # type: ignore
                list_entities_response["results"],
                {"total_entries": list_entities_response["total_entries"]},
            )

        @self.router.get(
            "/entities/{id}",
            summary="Retrieve an entity",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.entities.retrieve(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.entities.retrieve({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_entity(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedEntityResponse:
            """
            Retrieves detailed information about a specific entity by ID.
            """
            # FIXME: This is unacceptable. We need to check if the user has access to the entity.
            list_entities_response = await self.services["kg"].list_entities(
                user_ids=None,
                entity_ids=[id],
                offset=0,
                limit=1,
            )
            return list_entities_response["results"][0]

        @self.router.delete(
            "/entities/{id}",
            summary="Delete an entity",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.entities.delete(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.entities.delete({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def delete_entity(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Deletes an entity and all its associated data.

            This endpoint permanently removes:
            - The entity itself and all its attributes

            However, this will not remove any relationships or communities that the entity is part of.
            """
            # FIXME: This is unacceptable. We need to check if the user has access to the entity.
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            await self.services["kg"].delete_entity_v3(id=id)
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/entities/{id}",
            summary="Update an entity",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.entities.update(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                entity=entity,
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.entities.update({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    name: "Updated name",
                                    description: "Updated description",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def update_entity(
            id: UUID = Path(
                ...,
                description="The unique identifier of the entity to update",
            ),
            name: Optional[str] = Body(
                None,
                description="The name of the entity",
            ),
            description: Optional[str] = Body(
                None,
                description="The description of the entity",
            ),
            attributes: Optional[dict] = Body(
                None,
                description="The attributes of the entity",
            ),
            category: Optional[str] = Body(
                None,
                description="The category of the entity",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Update an existing entity.

            This endpoint allows updating the an existing entity.
            The user must have appropriate permissions to modify the entity.
            """
            # FIXME: This is unacceptable. We need to check if the user has access to the entity.

            return await self.services["kg"].update_entity(
                entity_id=id,
                name=name,
                description=description,
                category=category,
                attributes=attributes,
                user_id=auth_user.id,
            )
