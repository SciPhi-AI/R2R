# import json
# import logging
# import time
# from typing import Any, AsyncGenerator, Optional, Tuple
# from uuid import UUID
# from fastapi import HTTPException

# import asyncpg
# from asyncpg.exceptions import PostgresError, UndefinedTableError

# from core.base import (
#     Community,
#     Entity,
#     KGExtraction,
#     KGExtractionStatus,
#     GraphHandler,
#     R2RException,
#     Relationship,
# )
# from core.base.abstractions import (
#     CommunityInfo,
#     EntityLevel,
#     KGCreationSettings,
#     KGEnrichmentSettings,
#     KGEnrichmentStatus,
#     KGEntityDeduplicationSettings,
#     VectorQuantizationType,
# )

# from core.base.utils import _decorate_vector_type, llm_cost_per_million_tokens

# from .base import PostgresConnectionManager
# from .collection import PostgresCollectionHandler
# from .entity import PostgresEntityHandler
# from .relationship import PostgresRelationshipHandler
# from .community import PostgresCommunityHandler
# from .graph import PostgresGraphHandler

# logger = logging.getLogger()


# class PostgresGraphHandler(GraphHandler):
#     """Handler for Knowledge Graph METHODS in PostgreSQL."""

#     entity_handler: PostgresEntityHandler
#     relationship_handler: PostgresRelationshipHandler
#     community_handler: PostgresCommunityHandler
#     graph_handler: PostgresGraphHandler

#     def __init__(self, project_name: str, connection_manager: PostgresConnectionManager):
#         super().__init__(project_name, connection_manager)

