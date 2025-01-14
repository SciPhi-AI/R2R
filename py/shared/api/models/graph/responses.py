from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from shared.abstractions.graph import Community, Entity, Relationship
from shared.api.models.base import PaginatedR2RResult, R2RResults

WrappedEntityResponse = R2RResults[Entity]
WrappedEntitiesResponse = PaginatedR2RResult[list[Entity]]
WrappedRelationshipResponse = R2RResults[Relationship]
WrappedRelationshipsResponse = PaginatedR2RResult[list[Relationship]]
WrappedCommunityResponse = R2RResults[Community]
WrappedCommunitiesResponse = PaginatedR2RResult[list[Community]]


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
WrappedGraphResponse = R2RResults[GraphResponse]
WrappedGraphsResponse = PaginatedR2RResult[list[GraphResponse]]
