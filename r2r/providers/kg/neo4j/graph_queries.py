

UNIQUE_CONSTRAINTS = [
    "create constraint chunk_id if not exists for (c:__Chunk__) require c.id is unique;",
    "create constraint document_id if not exists for (d:__Document__) require d.id is unique;",
    "create constraint entity_id if not exists for (c:__Community__) require c.community is unique;",
    "create constraint entity_id if not exists for (e:__Entity__) require e.id is unique;",
    "create constraint entity_title if not exists for (e:__Entity__) require e.name is unique;",
    "create constraint entity_title if not exists for (e:__Covariate__) require e.title is unique;",
    "create constraint related_id if not exists for ()-[rel:RELATED]->() require rel.id is unique;"
]

GET_CHUNKS_QUERY = """
MATCH (c:__Chunk__)
RETURN c
"""

# class Fragment(BaseModel):
#     """A fragment extracted from a document."""

#     id: uuid.UUID
#     type: FragmentType
#     data: DataType
#     metadata: dict
#     document_id: uuid.UUID
#     extraction_id: uuid.UUID


PUT_CHUNKS_QUERY = """
MERGE (c:__Chunk__ {id:value.id})
SET c += value {.type, .data, .metadata, .document_id, .extraction_id}
MERGE (d:__Document__ {id:value.document_id})
MERGE (n)-[:PART_OF_DOCUMENT]->(d)
"""

# id: str
# category: str
# subcategory: Optional[str] = None
# value: str
# description: Optional[str] = None
# description_embedding: list[float] = None
# name_embedding: list[float] = None
# graph_embedding: list[float] = None
# community_ids: list[str] = None
# text_unit_ids: list[str] = None
# document_ids: list[str] = None
# rank: int | None = 1
# attributes: dict[str, Any] = None

# def __str__(self):
#     return (
#         f"{self.category}:{self.subcategory}:{self.value}"
#         if self.subcategory
#         else f"{self.category}:{self.value}"
#     )


GET_ENTITIES_QUERY = """
MATCH (e:__Entity__ {id:value.id})
WHERE $id IS NULL OR e.id = $id
RETURN e
"""

PUT_ENTITIES_QUERY = """
MERGE (e:__Entity__ {id:value.id})
SET e += value {.category, .subcategory, .value, .description, .rank, .attributes}
WITH e, value
CALL db.create.setNodeVectorProperty(e, "description_embedding", value.description_embedding)
CALL db.create.setNodeVectorProperty(e, "name_embedding", value.name_embedding)
CALL db.create.setNodeVectorProperty(e, "graph_embedding", value.graph_embedding)
CALL apoc.create.addLabels(e, [apoc.text.upperCamelCase(value.category)]) yield node
UNWIND value.text_unit_ids AS text_unit
MATCH (c:__Chunk__ {id:text_unit})
MERGE (c)-[:HAS_ENTITY]->(e)
WITH e, value
UNWIND value.document_ids AS document_id
MATCH (d:__Document__ {id:document_id})
MERGE (e)-[:APPEARS_IN]->(d)
WITH e, value
UNWIND value.community_ids AS community_id
MATCH (comm:__Community__ {community:community_id})
MERGE (e)-[:BELONGS_TO]->(comm)
"""


GET_RELATIONS_QUERY = """
MATCH (e:__Entity__ {name:replace(value.name,'"','')})
RETURN e
"""

PUT_RELATIONS_QUERY = """
MATCH (source:__Entity__ {name:replace(value.source,'"','')})
MATCH (target:__Entity__ {name:replace(value.target,'"','')})
// not necessary to merge on id as there is only one relationship per pair
MERGE (source)-[rel:RELATED {id: value.id}]->(target)
SET rel += value {.rank, .weight, .human_readable_id, .description, .text_unit_ids}
RETURN count(*) as createdRels
"""

GET_COMMUNITIES_QUERY = """
MATCH (c:__Community__ {community:value.id})
RETURN c
"""

PUT_COMMUNITIES_QUERY = """
MERGE (c:__Community__ {community:value.id})
SET c += value {.level, .title}
/*
UNWIND value.text_unit_ids as text_unit_id
MATCH (t:__Chunk__ {id:text_unit_id})
MERGE (c)-[:HAS_CHUNK]->(t)
WITH distinct c, value
*/
WITH *
UNWIND value.relationship_ids as rel_id
MATCH (start:__Entity__)-[:RELATED {id:rel_id}]->(end:__Entity__)
MERGE (start)-[:IN_COMMUNITY]->(c)
MERGE (end)-[:IN_COMMUNITY]->(c)
RETURN count(distinct c) as createdCommunities
"""

GET_COMMUNITIES_REPORT_QUERY = """
MATCH (c:__Community__ {community:value.community})
RETURN c
"""

PUT_COMMUNITIES_REPORT_QUERY = """
MERGE (c:__Community__ {community:value.community})
SET c += value {.level, .title, .rank, .rank_explanation, .full_content, .summary}
WITH c, value
UNWIND range(0, size(value.findings)-1) AS finding_idx
WITH c, value, finding_idx, value.findings[finding_idx] as finding
MERGE (c)-[:HAS_FINDING]->(f:Finding {id:finding_idx})
SET f += finding
"""

GET_COVARIATES_QUERY = """
MATCH (c:__Covariate__ {id:value.id})
RETURN c
"""

PUT_COVARIATES_QUERY = """
MERGE (c:__Covariate__ {id:value.id})
SET c += apoc.map.clean(value, ["text_unit_id", "document_ids", "n_tokens"], [NULL, ""])
WITH c, value
MATCH (ch:__Chunk__ {id: value.text_unit_id})
MERGE (ch)-[:HAS_COVARIATE]->(c)
"""