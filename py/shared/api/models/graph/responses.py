from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from shared.abstractions.graph import Community, Entity, Relationship
from shared.api.models.base import PaginatedR2RResult, R2RResults


class GraphResponse(BaseModel):
    id: UUID
    collection_id: UUID
    name: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    document_ids: list[UUID]


class Traversal(BaseModel):
    type: str
    id: UUID
    name: Optional[str]


class TraversalResponse(BaseModel):
    path: list[Traversal]
    total_cost: float
    num_hops: int


# Graph Responses
WrappedCommunityResponse = R2RResults[Community]
WrappedCommunitiesResponse = PaginatedR2RResult[list[Community]]

WrappedEntityResponse = R2RResults[Entity]
WrappedEntitiesResponse = PaginatedR2RResult[list[Entity]]

WrappedGraphResponse = R2RResults[GraphResponse]
WrappedGraphsResponse = PaginatedR2RResult[list[GraphResponse]]

WrappedRelationshipResponse = R2RResults[Relationship]
WrappedRelationshipsResponse = PaginatedR2RResult[list[Relationship]]

WrappedTraversalResponse = R2RResults[TraversalResponse]
