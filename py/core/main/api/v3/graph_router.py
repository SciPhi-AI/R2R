import logging
import textwrap
from typing import Optional, Union
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel, Field

from core.base import R2RException, RunType
from core.base.abstractions import EntityLevel, KGRunType
from core.base.api.models import (
    WrappedKGCreationResponse,
    WrappedKGEnrichmentResponse,
    WrappedKGEntityDeduplicationResponse,
    WrappedKGTunePromptResponse,
    WrappedKGRelationshipsResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from core.utils import (
    generate_default_user_collection_id,
    update_settings_from_dict,
)
from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper

from .base_router import BaseRouterV3

from fastapi import Request

logger = logging.getLogger()


class Entity(BaseModel):
    """Model representing a graph entity."""

    id: UUID
    name: str
    type: str
    metadata: dict = Field(default_factory=dict)
    level: EntityLevel
    collection_ids: list[UUID]
    embedding: Optional[list[float]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                "name": "John Smith",
                "type": "PERSON",
                "metadata": {"confidence": 0.95},
                "level": "DOCUMENT",
                "collection_ids": ["d09dedb1-b2ab-48a5-b950-6e1f464d83e7"],
                "embedding": [0.1, 0.2, 0.3],
            }
        }


class Relationship(BaseModel):
    """Model representing a graph relationship."""

    id: UUID
    subject_id: UUID
    object_id: UUID
    subject_name: str
    object_name: str
    predicate: str

class GraphRouter(BaseRouterV3):
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

    def _get_path_level(self, request: Request) -> EntityLevel:
        path = request.url.path
        if "/chunks/" in path:
            return EntityLevel.CHUNK
        elif "/documents/" in path:
            return EntityLevel.DOCUMENT
        else:
            return EntityLevel.COLLECTION

    def _setup_routes(self):
        ##### ENTITIES ######
        @self.router.get(
            "/chunks/{id}/entities",
            summary="List entities for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.list_entities(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=100)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.get(
            "/documents/{id}/entities",
            summary="List entities for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.list_entities(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=100)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.get(
            "/collections/{id}/entities",
            summary="List entities for a collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.list_entities(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=100)
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_entities(
            request: Request,
            id: UUID = Path(..., description="The ID of the chunk to retrieve entities for."),
            entity_names: Optional[list[str]] = Query(None, description="A list of entity names to filter the entities by."),
            entity_categories: Optional[list[str]] = Query(None, description="A list of entity categories to filter the entities by."),
            attributes: Optional[list[str]] = Query(None, description="A list of attributes to return. By default, all attributes are returned."),
            offset: int = Query(0, ge=0, description="The offset of the first entity to retrieve."),
            limit: int = Query(100, ge=0, le=20_000, description="The maximum number of entities to retrieve, up to 20,000."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[list[Entity]]:
            """
            Retrieves a list of entities associated with a specific chunk.  
            
            Note that when entities are extracted, neighboring chunks are also processed together to extract entities. 
            
            So, the entity returned here may not be in the same chunk as the one specified, but rather in a neighboring chunk (upto 2 chunks by default).   
            """
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            return await self.services["kg"].list_entities_v3(
                level=self._get_path_level(request),
                id=id,
                offset=offset,
                limit=limit,
                entity_names=entity_names,
                entity_categories=entity_categories,
                attributes=attributes
            )
        
        @self.router.post(
            "/chunks/{id}/entities",
            summary="Create entities for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.create_entities(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entities=[entity1, entity2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/documents/{id}/entities",
            summary="Create entities for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.create_entities(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entities=[entity1, entity2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/collections/{id}/entities",
            summary="Create entities for a collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.create_entities(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entities=[entity1, entity2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_entities(
            request: Request,
            id: UUID = Path(..., description="The ID of the chunk to create entities for."),
            entities: list[Union[Entity, dict]] = Body(..., description="The entities to create."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            entities = [Entity(**entity) if isinstance(entity, dict) else entity for entity in entities]
            # for each entity, set the level to CHUNK
            for entity in entities:
                if entity.level is None:
                    entity.level = EntityLevel.CHUNK
                else:
                    raise R2RException("Entity level must be chunk or empty.", 400)

            return await self.services["kg"].create_entities_v3(
                level=self._get_path_level(request),
                id=id,
                entities=entities,
            )

        @self.router.post(
            "/chunks/{id}/entities/{entity_id}",
            summary="Update an entity for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.update_entity(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000", entity=entity)
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_entity(
            request: Request,
            id: UUID = Path(..., description="The ID of the chunk to update the entity for."),
            entity_id: UUID = Path(..., description="The ID of the entity to update."),
            entity: Entity = Body(..., description="The updated entity."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            return await self.services["kg"].update_entity_v3(
                level=self._get_path_level(request),
                id=id,
                entity_id=entity_id,
                entity=entity,
            )

        @self.router.delete(
            "/chunks/{id}/entities/{entity_id}",
            summary="Delete an entity for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.delete_entity(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.delete(
            "/documents/{id}/entities/{entity_id}",
            summary="Delete an entity for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.delete_entity(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.delete(
            "/collections/{id}/entities/{entity_id}",
            summary="Delete an entity for a collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.delete_entity(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_entity(
            request: Request,
            id: UUID = Path(..., description="The ID of the chunk to delete the entity for."),
            entity_id: UUID = Path(..., description="The ID of the entity to delete."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            return await self.services["kg"].delete_entity_v3(
                level=self._get_path_level(request),
                id=id,
                entity_id=entity_id,
            )

        ##### RELATIONSHIPS #####
        @self.router.get(
            "/chunks/{id}/relationships",
            summary="List relationships for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.list_relationships(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.get(
            "/documents/{id}/relationships",
            summary="List relationships for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.list_relationships(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )

        @self.router.get(
            "/chunks/{id}/relationships",
            summary="List relationships for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.list_relationships(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_relationships(
            id: UUID = Path(..., description="The ID of the chunk to retrieve relationships for."),
            entity_names: Optional[list[str]] = Query(None, description="A list of entity names to filter the relationships by."),
            relationship_types: Optional[list[str]] = Query(None, description="A list of relationship types to filter the relationships by."),
            attributes: Optional[list[str]] = Query(None, description="A list of attributes to return. By default, all attributes are returned."),
            offset: int = Query(0, ge=0, description="The offset of the first relationship to retrieve."),
            limit: int = Query(100, ge=0, le=20_000, description="The maximum number of relationships to retrieve, up to 20,000."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[list[Relationship]]:
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            return await self.services["kg"].list_relationships_v3(
                level=EntityLevel.CHUNK,
                id=id,
                entity_names=entity_names,
                relationship_types=relationship_types,
                attributes=attributes,
                offset=offset,
                limit=limit,
            )


        @self.router.post(
            "/chunks/{id}/relationships",
            summary="Create relationships for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.create_relationships(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationships=[relationship1, relationship2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_relationships(
            id: UUID = Path(..., description="The ID of the chunk to create relationships for."),
            relationships: list[Union[Relationship, dict]] = Body(..., description="The relationships to create."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGRelationshipsResponse:
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            relationships = [Relationship(**relationship) if isinstance(relationship, dict) else relationship for relationship in relationships]

            return await self.services["kg"].create_relationships_v3(
                level=EntityLevel.CHUNK,
                id=id,
                relationships=relationships,
            )
        

        @self.router.post(
            "/chunks/{id}/relationships/{relationship_id}",
            summary="Update a relationship for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.update_relationship(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000", relationship=relationship)
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint 
        async def update_relationship(
            id: UUID = Path(..., description="The ID of the chunk to update the relationship for."),
            relationship_id: UUID = Path(..., description="The ID of the relationship to update."),
            relationship: Relationship = Body(..., description="The updated relationship."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)


            return await self.services["kg"].update_relationship_v3(
                level=EntityLevel.CHUNK,
                id=id,
                relationship_id=relationship_id,
                relationship=relationship,
            )

        @self.router.delete(
            "/chunks/{id}/relationships/{relationship_id}",
            summary="Delete a relationship for a chunk",
        )
        @self.base_endpoint
        async def delete_relationship(
            id: UUID = Path(..., description="The ID of the chunk to delete the relationship for."),
            relationship_id: UUID = Path(..., description="The ID of the relationship to delete."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            return await self.services["kg"].delete_relationship_v3(
                level=EntityLevel.CHUNK,
                id=id,
                relationship_id=relationship_id,
            )

        ##### DOCUMENT LEVEL OPERATIONS #####
        @self.router.get(
            "/documents/{id}/entities",
            summary="List entities for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.list_entities(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=100)
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_entities(
            id: UUID = Path(..., description="The ID of the document to retrieve entities for."),
            entity_names: Optional[list[str]] = Query(None, description="A list of entity names to filter the entities by."),
            entity_categories: Optional[list[str]] = Query(None, description="A list of entity categories to filter the entities by."),
            attributes: Optional[list[str]] = Query(None, description="A list of attributes to return. By default, all attributes are returned."),
            offset: int = Query(0, ge=0, description="The offset of the first entity to retrieve."),
            limit: int = Query(100, ge=0, le=20_000, description="The maximum number of entities to retrieve, up to 20,000."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[list[Entity]]:
            """
            Retrieves a list of entities associated with a specific document.  
            """
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            return await self.services["kg"].list_entities_v3(
                level=EntityLevel.DOCUMENT,
                id=id,
                offset=offset,
                limit=limit,
                entity_names=entity_names,
                entity_categories=entity_categories,
                attributes=attributes
            )
        
        @self.router.post(
            "/documents/{id}/entities",
            summary="Create entities for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.create_entities(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entities=[entity1, entity2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_entities(
            id: UUID = Path(..., description="The ID of the chunk to create entities for."),
            entities: list[Union[Entity, dict]] = Body(..., description="The entities to create."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            entities = [Entity(**entity) if isinstance(entity, dict) else entity for entity in entities]
            # for each entity, set the level to CHUNK
            for entity in entities:
                if entity.level is None:
                    entity.level = EntityLevel.DOCUMENT
                else:
                    raise R2RException("Entity level must be chunk or empty.", 400)

            return await self.services["kg"].create_entities_v3(
                level=EntityLevel.DOCUMENT,
                id=id,
                entities=entities,
            )

        @self.router.post(
            "/documents/{id}/entities/{entity_id}",
            summary="Update an entity for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.update_entity(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000", entity=entity)
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_entity(
            id: UUID = Path(..., description="The ID of the document to update the entity for."),
            entity_id: UUID = Path(..., description="The ID of the entity to update."),
            entity: Entity = Body(..., description="The updated entity."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            return await self.services["kg"].update_entity_v3(
                level=EntityLevel.DOCUMENT,
                id=id,
                entity_id=entity_id,
                entity=entity,
            )


        @self.router.delete(
            "/documents/{id}/entities/{entity_id}",
            summary="Delete an entity for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.delete_entity(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
        )

        @self.base_endpoint
        async def delete_entity(
            id: UUID = Path(..., description="The ID of the document to delete the entity for."),
            entity_id: UUID = Path(..., description="The ID of the entity to delete."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

        ##### RELATIONSHIPS #####
        @self.router.get(
            "/documents/{id}/relationships",
            summary="List relationships for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.list_relationships(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_relationships(
            id: UUID = Path(..., description="The ID of the document to retrieve relationships for."),
            entity_names: Optional[list[str]] = Query(None, description="A list of entity names to filter the relationships by."),
            relationship_types: Optional[list[str]] = Query(None, description="A list of relationship types to filter the relationships by."),
            attributes: Optional[list[str]] = Query(None, description="A list of attributes to return. By default, all attributes are returned."),
            offset: int = Query(0, ge=0, description="The offset of the first relationship to retrieve."),
            limit: int = Query(100, ge=0, le=20_000, description="The maximum number of relationships to retrieve, up to 20,000."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[list[Relationship]]:
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            return await self.services["kg"].list_relationships_v3(
                level=EntityLevel.DOCUMENT,
                id=id,
                entity_names=entity_names,
                relationship_types=relationship_types,
                attributes=attributes,
                offset=offset,
                limit=limit,
            )


        @self.router.post(
            "/documents/{id}/relationships",
            summary="Create relationships for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.create_relationships(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationships=[relationship1, relationship2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_relationships(
            id: UUID = Path(..., description="The ID of the document to create relationships for."),
            relationships: list[Union[Relationship, dict]] = Body(..., description="The relationships to create."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[list[RelationshipResponse]]:
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            relationships = [Relationship(**relationship) if isinstance(relationship, dict) else relationship for relationship in relationships]

            return await self.services["kg"].create_relationships_v3(
                level=EntityLevel.DOCUMENT,
                id=id,
                relationships=relationships,
            )
        

        @self.router.post(
            "/documents/{id}/relationships/{relationship_id}",
            summary="Update a relationship for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.update_relationship(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000", relationship=relationship)
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint 
        async def update_relationship(
            id: UUID = Path(..., description="The ID of the document to update the relationship for."),
            relationship_id: UUID = Path(..., description="The ID of the relationship to update."),
            relationship: Relationship = Body(..., description="The updated relationship."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)


            return await self.services["kg"].update_relationship_v3(
                level=EntityLevel.DOCUMENT,
                id=id,
                relationship_id=relationship_id,
                relationship=relationship,
            )

        @self.router.delete(
            "/documents/{id}/relationships/{relationship_id}",
            summary="Delete a relationship for a document",
        )
        @self.base_endpoint
        async def delete_relationship(
            id: UUID = Path(..., description="The ID of the document to delete the relationship for."),
            relationship_id: UUID = Path(..., description="The ID of the relationship to delete."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            return await self.services["kg"].delete_relationship_v3(
                level=EntityLevel.DOCUMENT,
                id=id,
                relationship_id=relationship_id,
            )

        ##### COLLECTION LEVEL OPERATIONS #####






        # Graph-level operations
        @self.router.post(
            "/graphs/{collection_id}",
            summary="Create a new graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.create(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                settings={
                                    "entity_types": ["PERSON", "ORG", "GPE"]
                                }
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "settings": {
                                        "entity_types": ["PERSON", "ORG", "GPE"]
                                    }
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_graph(
            collection_id: UUID = Path(
                default=...,
                description="Collection ID to create graph for.",
            ),
            run_type: Optional[KGRunType] = Body(
                default=None,
                description="Run type for the graph creation process.",
            ),
            settings: Optional[KGCreationSettings] = Body(
                default=None,
                description="Settings for the graph creation process.",
            ),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGCreationResponse:
            """Creates a new knowledge graph by extracting entities and relationships from documents in a collection.

            The graph creation process involves:
            1. Parsing documents into semantic chunks
            2. Extracting entities and relationships using LLMs or NER
            3. Building a connected knowledge graph structure
            """

            settings = settings.dict() if settings else None
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            logger.info(f"Running create-graph on collection {collection_id}")

            # If no collection ID is provided, use the default user collection
            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            # If no run type is provided, default to estimate
            if not run_type:
                run_type = KGRunType.ESTIMATE

            # Apply runtime settings overrides
            server_kg_creation_settings = (
                self.providers.database.config.kg_creation_settings
            )

            if settings:
                server_kg_creation_settings = update_settings_from_dict(
                    server_kg_creation_settings, settings
                )

            # If the run type is estimate, return an estimate of the creation cost
            if run_type is KGRunType.ESTIMATE:
                return await self.services["kg"].get_creation_estimate(
                    collection_id, server_kg_creation_settings
                )
            else:

                # Otherwise, create the graph
                if run_with_orchestration:
                    workflow_input = {
                        "collection_id": str(collection_id),
                        "kg_creation_settings": server_kg_creation_settings.model_dump_json(),
                        "user": auth_user.json(),
                    }

                    return await self.orchestration_provider.run_workflow(  # type: ignore
                        "create-graph", {"request": workflow_input}, {}
                    )
                else:
                    from core.main.orchestration import simple_kg_factory

                    logger.info("Running create-graph without orchestration.")
                    simple_kg = simple_kg_factory(self.service)
                    await simple_kg["create-graph"](workflow_input)
                    return {
                        "message": "Graph created successfully.",
                        "task_id": None,
                    }

        @self.router.get(
            "/graphs/{collection_id}",
            summary="Get graph status",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.get_status(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_graph_status(
            collection_id: UUID = Path(...),  # TODO: change to id?
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[dict]:
            """
            Gets the status and metadata of a graph for a collection.

            Returns information about:
            - Creation status and timestamp
            - Enrichment status and timestamp
            - Entity and relationship counts
            - Community statistics
            - Current settings
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can view graph status", 403
                )

            # status = await self.services["kg"].get_graph_status(collection_id)
            # return status  # type: ignore

        # @self.router.post(
        #     "/graphs/{collection_id}/enrich",
        #     summary="Enrich an existing graph",
        #     openapi_extra={
        #         "x-codeSamples": [
        #             {
        #                 "lang": "Python",
        #                 "source": textwrap.dedent(
        #                     """
        #                     from r2r import R2RClient

        #                     client = R2RClient("http://localhost:7272")
        #                     # when using auth, do client.login(...)

        #                     result = client.graphs.enrich(
        #                         collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
        #                         settings={
        #                             "community_detection": {
        #                                 "algorithm": "louvain",
        #                                 "resolution": 1.0
        #                             },
        #                             "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
        #                         }
        #                     )"""
        #                 ),
        #             },
        #             {
        #                 "lang": "cURL",
        #                 "source": textwrap.dedent(
        #                     """
        #                     curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/enrich" \\
        #                         -H "Content-Type: application/json" \\
        #                         -H "Authorization: Bearer YOUR_API_KEY" \\
        #                         -d '{
        #                             "settings": {
        #                                 "community_detection": {
        #                                     "algorithm": "louvain",
        #                                     "resolution": 1.0
        #                                 },
        #                                 "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
        #                             }
        #                         }'"""
        #                 ),
        #             },
        #         ]
        #     },
        # )
        # @self.base_endpoint
        # async def enrich_graph(
        #     collection_id: UUID = Path(...),
        #     settings: Optional[dict] = Body(None),
        #     run_with_orchestration: bool = Query(True),
        #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # ) -> ResultsWrapper[WrappedKGEnrichmentResponse]:
        #     """Enriches an existing graph with additional information and creates communities."""
        #     if not auth_user.is_superuser:
        #         raise R2RException("Only superusers can enrich graphs", 403)

        #     server_settings = self.providers.database.config.kg_enrichment_settings
        #     if settings:
        #         server_settings = update_settings_from_dict(server_settings, settings)

        #     workflow_input = {
        #         "collection_id": str(collection_id),
        #         "kg_enrichment_settings": server_settings.model_dump_json(),
        #         "user": auth_user.model_dump_json(),
        #     }

        #     if run_with_orchestration:
        #         return await self.orchestration_provider.run_workflow(
        #             "enrich-graph", {"request": workflow_input}, {}
        #         )
        #     else:
        #         from core.main.orchestration import simple_kg_factory
        #         simple_kg = simple_kg_factory(self.services["kg"])
        #         await simple_kg["enrich-graph"](workflow_input)
        #         return {"message": "Graph enriched successfully.", "task_id": None}

        @self.router.delete(
            "/graphs/{collection_id}",
            summary="Delete a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.delete(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                cascade=True
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7?cascade=true" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_graph(
            collection_id: UUID = Path(...),
            cascade: bool = Query(False),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[dict]:
            """Deletes a graph and optionally its associated entities and relationships."""
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can delete graphs", 403)

            await self.services["kg"].delete_graph(collection_id, cascade)
            return {"message": "Graph deleted successfully"}  # type: ignore

        # Entity operations
        @self.router.post(
            "/graphs/{collection_id}/entities/{level}",
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

                            result = client.graphs.create_entity(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                entity={
                                    "name": "John Smith",
                                    "type": "PERSON",
                                    "metadata": {
                                        "source": "manual",
                                        "confidence": 1.0
                                    },
                                }
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/entities/document" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "name": "John Smith",
                                    "type": "PERSON",
                                    "metadata": {
                                        "source": "manual",
                                        "confidence": 1.0
                                    },
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_entity(
            collection_id: UUID = Path(...),
            entity: dict = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[Entity]:
            """Creates a new entity in the graph."""
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can create entities", 403)

            new_entity = await self.services["kg"].create_entity(
                collection_id, entity
            )
            return new_entity  # type: ignore

        @self.router.delete(
            "/graphs/{collection_id}/entities/{entity_id}",
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

                            result = client.graphs.delete_entity(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                entity_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                cascade=True
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/entities/9fbe403b-c11c-5aae-8ade-ef22980c3ad1?cascade=true" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_entity(
            collection_id: UUID = Path(...),
            entity_id: UUID = Path(...),
            cascade: bool = Query(
                False,
                description="Whether to also delete related relationships",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[dict]:
            """Deletes an entity and optionally its relationships."""
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can delete entities", 403)

            # await self.services["kg"].delete_entity(
            #     collection_id, entity_id, cascade
            # )
            # return {"message": "Entity deleted successfully"}  # type: ignore

        @self.router.get(
            "/graphs/{collection_id}/entities",
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

                            result = client.graphs.list_entities(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                level="DOCUMENT",
                                offset=0,
                                limit=100,
                                include_embeddings=False
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/entities?\\
                                level=DOCUMENT&offset=0&limit=100&include_embeddings=false" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_entities(
            collection_id: UUID = Path(...),
            level: EntityLevel = Query(EntityLevel.DOCUMENT),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            include_embeddings: bool = Query(False),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> (
            WrappedKGEntitiesResponse
        ):  # PaginatedResultsWrapper[list[Entity]]:
            """Lists entities in the graph with filtering and pagination support.

            Entities represent the nodes in the knowledge graph, extracted from documents.
            Each entity has:
            - Unique identifier and name
            - Entity type (e.g. PERSON, ORG, LOCATION)
            - Source documents and extractions
            - Generated description
            - Community memberships
            - Optional vector embedding
            """
            entities = await self.services["kg"].list_entities(
                collection_id, level, offset, limit, include_embeddings
            )
            return entities  # type: ignore

        @self.router.get(
            "/graphs/{collection_id}/entities/{entity_id}",
            summary="Get entity details",
        )
        @self.base_endpoint
        async def get_entity(
            collection_id: UUID = Path(...),
            level: EntityLevel = Query(EntityLevel.DOCUMENT),
            entity_id: int = Path(...),
            # include_embeddings: bool = Query(False),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[Entity]:
            """Retrieves details of a specific entity."""
            entity = await self.services["kg"].get_entity(
                collection_id, entity_id, include_embeddings
            )
            if not entity:
                raise R2RException("Entity not found", 404)
            return entity

        @self.router.post(
            "/graphs/{collection_id}/entities/{entity_id}",
            summary="Update entity",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.update_entity(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                entity_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                entity_update={
                                    "name": "Updated Entity Name",
                                    "metadata": {
                                        "confidence": 0.95,
                                        "source": "manual_correction"
                                    }
                                }
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/entities/9fbe403b-c11c-5aae-8ade-ef22980c3ad1" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "name": "Updated Entity Name",
                                    "metadata": {
                                        "confidence": 0.95,
                                        "source": "manual_correction"
                                    }
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_entity(
            collection_id: UUID = Path(...),
            entity_id: UUID = Path(...),
            entity_update: dict = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[Entity]:
            """Updates an existing entity."""
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can update entities", 403)

            # updated_entity = await self.services["kg"].update_entity(
            #     collection_id, entity_id, entity_update
            # )
            # return updated_entity  # type: ignore

        @self.router.post(
            "/graphs/{collection_id}/entities/deduplicate",
            summary="Deduplicate entities in the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.deduplicate_entities(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                settings={
                                    "kg_entity_deduplication_type": "by_name",
                                    "kg_entity_deduplication_prompt": "default",
                                    "generation_config": {
                                        "model": "openai/gpt-4o-mini",
                                        "temperature": 0.12
                                    },
                                    "max_description_input_length": 65536
                                }
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/entities/deduplicate" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "settings": {
                                        "kg_entity_deduplication_type": "by_name",
                                        "kg_entity_deduplication_prompt": "default",
                                        "max_description_input_length": 65536,
                                        "generation_config": {
                                            "model": "openai/gpt-4o-mini",
                                            "temperature": 0.12
                                        }
                                    }
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def deduplicate_entities(
            collection_id: UUID = Path(...),
            settings: Optional[dict] = Body(None),
            run_type: Optional[KGRunType] = Query(
                KGRunType.ESTIMATE,
                description="Whether to estimate cost or run deduplication",
            ),
            run_with_orchestration: bool = Query(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[WrappedKGEntityDeduplicationResponse]:
            """Deduplicates entities in the knowledge graph using LLM-based analysis.

            The deduplication process:
            1. Groups potentially duplicate entities by name/type
            2. Uses LLM analysis to determine if entities refer to same thing
            3. Merges duplicate entities while preserving relationships
            4. Updates all references to use canonical entity IDs

            Args:
                collection_id (UUID): Collection containing the graph
                settings (dict, optional): Deduplication settings including:
                    - kg_entity_deduplication_type (str): Deduplication method (e.g. "by_name")
                    - kg_entity_deduplication_prompt (str): Custom prompt for analysis
                    - max_description_input_length (int): Max chars for entity descriptions
                    - generation_config (dict): LLM generation parameters
                run_type (KGRunType): Whether to estimate cost or run deduplication
                run_with_orchestration (bool): Whether to run async with task queue
                auth_user: Authenticated user making request

            Returns:
                Result containing:
                    message (str): Status message
                    task_id (UUID): Async task ID if run with orchestration

            Raises:
                R2RException: If user unauthorized or deduplication fails
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can deduplicate entities", 403
                )

            server_settings = (
                self.providers.database.config.kg_entity_deduplication_settings
            )
            if settings:
                server_settings = update_settings_from_dict(
                    server_settings, settings
                )

            # Return cost estimate if requested
            if run_type == KGRunType.ESTIMATE:
                return await self.services["kg"].get_deduplication_estimate(
                    collection_id, server_settings
                )

            workflow_input = {
                "collection_id": str(collection_id),
                "kg_entity_deduplication_settings": server_settings.model_dump_json(),
                "user": auth_user.model_dump_json(),
            }

            if run_with_orchestration:
                return await self.orchestration_provider.run_workflow(  # type: ignore
                    "entity-deduplication", {"request": workflow_input}, {}
                )
            else:
                from core.main.orchestration import simple_kg_factory

                simple_kg = simple_kg_factory(self.services["kg"])
                await simple_kg["entity-deduplication"](workflow_input)
                return {  # type: ignore
                    "message": "Entity deduplication completed successfully.",
                    "task_id": None,
                }

        @self.router.post(
            "/graphs/{document_id}/relationships",
            summary="Create a new relationship",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.create_relationship(
                                document_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                relationship={
                                    "source_id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    "target_id": "7cde891f-2a3b-4c5d-6e7f-gh8i9j0k1l2m",
                                    "type": "WORKS_FOR",
                                    "metadata": {
                                        "source": "manual",
                                        "confidence": 1.0
                                    }
                                }
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/relationships" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "source_id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    "target_id": "7cde891f-2a3b-4c5d-6e7f-gh8i9j0k1l2m",
                                    "type": "WORKS_FOR",
                                    "metadata": {
                                        "source": "manual",
                                        "confidence": 1.0
                                    }
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_relationship(
            relationship: dict = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[Relationship]:
            """Creates a new relationship between entities."""
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can create relationships", 403
                )

            new_relationship = await self.services["kg"].create_relationship(
                collection_id, relationship
            )
            return new_relationship  # type: ignore

        # Relationship operations
        @self.router.get(
            "/graphs/{collection_id}/relationships",
            summary="List relationships",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.list_relationships(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                source_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                relationship_type="WORKS_FOR",
                                offset=0,
                                limit=100
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/relationships?\\
                                source_id=9fbe403b-c11c-5aae-8ade-ef22980c3ad1&\\
                                relationship_type=WORKS_FOR&offset=0&limit=100" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_relationships(
            collection_id: UUID = Path(...),
            source_id: Optional[UUID] = Query(None),
            target_id: Optional[UUID] = Query(None),
            relationship_type: Optional[str] = Query(None),
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
        ) -> PaginatedResultsWrapper[list[Relationship]]:
            """Lists relationships (edges) between entities in the knowledge graph.

            Relationships represent connections between entities with:
            - Source and target entities
            - Relationship type and description
            - Confidence score and metadata
            - Source documents and extractions
            """
            raise R2RException("Not implemented", 501)
            # relationships = await self.services["kg"].list_relationships(
            #     collection_id,
            #     source_id,
            #     target_id,
            #     relationship_type,
            #     offset,
            #     limit,
            # )
            # return relationships  # type: ignore

        @self.router.get(
            "/graphs/{collection_id}/relationships/{relationship_id}",
            summary="Get relationship details",
        )
        @self.base_endpoint
        async def get_relationship(
            collection_id: UUID = Path(...),
            relationship_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[Relationship]:
            """Retrieves details of a specific relationship."""
            raise R2RException("Not implemented", 501)
            # relationship = await self.services["kg"].get_relationship(
            #     collection_id, relationship_id
            # )
            # if not relationship:
            #     raise R2RException("Relationship not found", 404)
            # return relationship  # type: ignore

        @self.router.post(
            "/graphs/{collection_id}/relationships/{relationship_id}",
            summary="Update relationship",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.update_relationship(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                relationship_id="8abc123d-ef45-678g-hi90-jklmno123456",
                                relationship_update={
                                    "type": "EMPLOYED_BY",
                                    "metadata": {
                                        "confidence": 0.95,
                                        "source": "manual_correction"
                                    }
                                }
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/relationships/8abc123d-ef45-678g-hi90-jklmno123456" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "type": "EMPLOYED_BY",
                                    "metadata": {
                                        "confidence": 0.95,
                                        "source": "manual_correction"
                                    }
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_relationship(
            collection_id: UUID = Path(...),
            relationship_id: UUID = Path(...),
            relationship_update: dict = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[Relationship]:
            """Updates an existing relationship."""
            raise NotImplementedError("Not implemented")
            # if not auth_user.is_superuser:
            #     raise R2RException(
            #         "Only superusers can update relationships", 403
            #     )

            updated_relationship = await self.services[
                "kg"
            ].update_relationship(
                collection_id, relationship_id, relationship_update
            )
            return updated_relationship  # type: ignore

        @self.router.delete(
            "/graphs/{collection_id}/relationships/{relationship_id}",
            summary="Delete a relationship",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.delete_relationship(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                relationship_id="8abc123d-ef45-678g-hi90-jklmno123456"
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/relationships/8abc123d-ef45-678g-hi90-jklmno123456" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_relationship(
            collection_id: UUID = Path(...),
            relationship_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[dict]:
            """Deletes a relationship."""
            raise NotImplementedError("Not implemented")
            # if not auth_user.is_superuser:
            #     raise R2RException(
            #         "Only superusers can delete relationships", 403
            #     )

            # await self.services["kg"].delete_relationship(
            #     collection_id, relationship_id
            # )
            # return {"message": "Relationship deleted successfully"}  # type: ignore

        # Community operations
        @self.router.post(
            "/graphs/{collection_id}/communities",
            summary="Create communities in the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.create_communities(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                settings={
                                    "max_summary_input_length": 65536,
                                }
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities/create" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "settings": {
                                        "max_summary_input_length": 65536,
                                    }
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_communities(
            collection_id: UUID = Path(...),
            settings: Optional[dict] = Body(None),
            run_type: Optional[KGRunType] = Body(
                default=None,
                description="Run type for the graph creation process.",
            ),
            run_with_orchestration: bool = Query(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGEnrichmentResponse:
            """Creates communities in the graph by analyzing entity relationships and similarities.

            Communities are created by:
            1. Builds similarity graph between entities
            2. Applies community detection algorithm (e.g. Leiden)
            3. Creates hierarchical community levels
            4. Generates summaries and insights for each community
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can create communities", 403
                )

            # Apply runtime settings overrides
            server_kg_enrichment_settings = (
                self.providers.database.config.kg_enrichment_settings
            )
            if settings:
                server_kg_enrichment_settings = update_settings_from_dict(
                    server_kg_enrichment_settings, settings
                )

            workflow_input = {
                "collection_id": str(collection_id),
                "kg_enrichment_settings": server_kg_enrichment_settings.model_dump_json(),
                "user": auth_user.model_dump_json(),
            }

            if not run_type:
                run_type = KGRunType.ESTIMATE

            # If the run type is estimate, return an estimate of the enrichment cost
            if run_type is KGRunType.ESTIMATE:
                return await self.services["kg"].get_enrichment_estimate(
                    collection_id, server_kg_enrichment_settings
                )

            else:
                if run_with_orchestration:
                    return await self.orchestration_provider.run_workflow(  # type: ignore
                        "enrich-graph", {"request": workflow_input}, {}
                    )
                else:
                    from core.main.orchestration import simple_kg_factory

                    simple_kg = simple_kg_factory(self.services["kg"])
                    await simple_kg["enrich-graph"](workflow_input)
                    return {  # type: ignore
                        "message": "Communities created successfully.",
                        "task_id": None,
                    }

        @self.router.post(
            "/graphs/{collection_id}/communities/{community_id}",
            summary="Update community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.update_community(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                community_id="5xyz789a-bc12-3def-4ghi-jk5lm6no7pq8",
                                community_update={
                                    "metadata": {
                                        "topic": "Technology",
                                        "description": "Tech companies and products"
                                    }
                                }
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities/5xyz789a-bc12-3def-4ghi-jk5lm6no7pq8" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "metadata": {
                                        "topic": "Technology",
                                        "description": "Tech companies and products"
                                    }
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_community(
            collection_id: UUID = Path(...),
            community_id: UUID = Path(...),
            community_update: dict = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[Community]:
            """Updates a community's metadata."""
            raise NotImplementedError("Not implemented")
            # if not auth_user.is_superuser:
            #     raise R2RException(
            #         "Only superusers can update communities", 403
            #     )

            # updated_community = await self.services["kg"].update_community(
            #     collection_id, community_id, community_update
            # )
            # return updated_community  # type: ignore

        @self.router.get(
            "/graphs/{collection_id}/communities",
            summary="List communities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.list_communities(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                level=1,
                                offset=0,
                                limit=100
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities?\\
                                level=1&offset=0&limit=100" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_communities(
            collection_id: UUID = Path(...),
            level: Optional[int] = Query(None),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> (
            WrappedKGCommunitiesResponse
        ):  # PaginatedResultsWrapper[list[Community]]:
            """Lists communities in the graph with optional filtering and pagination.

            Each community represents a group of related entities with:
            - Community number and hierarchical level
            - Member entities and relationships
            - Generated name and summary
            - Key findings and insights
            - Impact rating and explanation
            """
            communities = await self.services["kg"].list_communities(
                collection_id, levels, community_numbers, offset, limit
            )
            return communities  # type: ignore

        @self.router.get(
            "/graphs/{collection_id}/communities/{community_id}",
            summary="Get community details",
        )
        @self.base_endpoint
        async def get_community(
            collection_id: UUID = Path(...),
            community_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[Community]:
            """Retrieves details of a specific community."""
            raise NotImplementedError("Not implemented")
            # community = await self.services["kg"].get_community(
            #     collection_id, community_id
            # )
            # if not community:
            #     raise R2RException("Community not found", 404)
            # return community  # type: ignore

        @self.router.delete(
            "/graphs/{collection_id}/communities",
            summary="Delete all communities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            # Delete all communities
                            result = client.graphs.delete_communities(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )

                            # Delete specific level
                            result = client.graphs.delete_communities(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                level=1
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            # Delete all communities
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities" \\
                                -H "Authorization: Bearer YOUR_API_KEY"

                            # Delete specific level
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities?level=1" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_communities(
            collection_id: UUID = Path(...),
            level: Optional[int] = Query(
                None,
                description="Specific community level to delete. If not provided, all levels will be deleted.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[dict]:
            """
            Deletes communities from the graph. Can delete all communities or a specific level.
            This is useful when you want to recreate communities with different parameters.
            """
            raise NotImplementedError("Not implemented")
            # if not auth_user.is_superuser:
            #     raise R2RException(
            #         "Only superusers can delete communities", 403
            #     )

            # await self.services["kg"].delete_communities(collection_id, level)

            # if level is not None:
            #     return {  # type: ignore
            #         "message": f"Communities at level {level} deleted successfully"
            #     }
            # return {"message": "All communities deleted successfully"}  # type: ignore

        @self.router.delete(
            "/graphs/{collection_id}/communities/{community_id}",
            summary="Delete a specific community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.delete_community(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                community_id="5xyz789a-bc12-3def-4ghi-jk5lm6no7pq8"
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities/5xyz789a-bc12-3def-4ghi-jk5lm6no7pq8" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_community(
            collection_id: UUID = Path(...),
            community_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Deletes a specific community by ID.
            This operation will not affect other communities or the underlying entities.
            """
            raise NotImplementedError("Not implemented")
            # if not auth_user.is_superuser:
            #     raise R2RException(
            #         "Only superusers can delete communities", 403
            #     )

            # # First check if community exists
            # community = await self.services["kg"].get_community(
            #     collection_id, community_id
            # )
            # if not community:
            #     raise R2RException("Community not found", 404)

            await self.services["kg"].delete_community(
                collection_id, community_id
            )
            return True  # type: ignore

        @self.router.post(
            "/graphs/{collection_id}/tune-prompt",
            summary="Tune a graph-related prompt",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.tune_prompt(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                prompt_name="graphrag_relationships_extraction_few_shot",
                                documents_limit=100,
                                chunks_limit=1000
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/tune-prompt" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "prompt_name": "graphrag_relationships_extraction_few_shot",
                                    "documents_limit": 100,
                                    "chunks_limit": 1000
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def tune_prompt(
            collection_id: UUID = Path(...),
            prompt_name: str = Body(
                ...,
                description="The prompt to tune. Valid options: graphrag_relationships_extraction_few_shot, graphrag_entity_description, graphrag_community_reports",
            ),
            documents_offset: int = Body(0, ge=0),
            documents_limit: int = Body(100, ge=1),
            chunks_offset: int = Body(0, ge=0),
            chunks_limit: int = Body(100, ge=1),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGTunePromptResponse:
            """Tunes a graph operation prompt using collection data.

            Uses sample documents and chunks from the collection to tune prompts for:
            - Entity and relationship extraction
            - Entity description generation
            - Community report generation
            """
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can tune prompts", 403)

            tuned_prompt = await self.services["kg"].tune_prompt(
                prompt_name=prompt_name,
                collection_id=collection_id,
                documents_offset=documents_offset,
                documents_limit=documents_limit,
                chunks_offset=chunks_offset,
                chunks_limit=chunks_limit,
            )

            return tuned_prompt  # type: ignore
