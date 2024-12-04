from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from shared.abstractions.graph import Community, Entity, Relationship
from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper

WrappedEntityResponse = ResultsWrapper[Entity]
WrappedEntitiesResponse = PaginatedResultsWrapper[list[Entity]]
WrappedRelationshipResponse = ResultsWrapper[Relationship]
WrappedRelationshipsResponse = PaginatedResultsWrapper[list[Relationship]]
WrappedCommunityResponse = ResultsWrapper[Community]
WrappedCommunitiesResponse = PaginatedResultsWrapper[list[Community]]


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
WrappedGraphResponse = ResultsWrapper[GraphResponse]
WrappedGraphsResponse = PaginatedResultsWrapper[list[GraphResponse]]
