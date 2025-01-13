from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from shared.abstractions.graph import Community, Entity, Relationship
from shared.api.models.base import PaginatedFUSEResult, FUSEResults

WrappedEntityResponse = FUSEResults[Entity]
WrappedEntitiesResponse = PaginatedFUSEResult[list[Entity]]
WrappedRelationshipResponse = FUSEResults[Relationship]
WrappedRelationshipsResponse = PaginatedFUSEResult[list[Relationship]]
WrappedCommunityResponse = FUSEResults[Community]
WrappedCommunitiesResponse = PaginatedFUSEResult[list[Community]]


class GraphResponse(BaseModel):
    id: UUID
    collection_id: UUID
    name: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    document_ids: list[UUID]


# Graph Responses
WrappedGraphResponse = FUSEResults[GraphResponse]
WrappedGraphsResponse = PaginatedFUSEResult[list[GraphResponse]]
