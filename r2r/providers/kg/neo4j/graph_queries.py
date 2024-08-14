

UNIQUE_CONSTRAINTS = [
    # "create constraint chunk_id if not exists for (c:__Chunk__) require c.id is unique;",
    # "create constraint document_id if not exists for (d:__Document__) require d.id is unique;",
    # "create constraint entity_id if not exists for (c:__Community__) require c.community is unique;",
    # "create constraint entity_id if not exists for (e:__Entity__) require e.id is unique;",
    # "create constraint entity_title if not exists for (e:__Entity__) require e.name is unique;",
    # "create constraint entity_title if not exists for (e:__Covariate__) require e.title is unique;",
    # "create constraint related_id if not exists for ()-[rel:RELATED]->() require rel.id is unique;"
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
MATCH (e:__Entity__)
WHERE size($entity_ids) = 0 OR e.id IN $entity_ids
RETURN e
"""

PUT_ENTITIES_QUERY = """
CALL apoc.merge.node(['__Entity__', value.category], {name: value.name, id: value.id}) YIELD node as e
SET e += value {.description, .rank, .attributes}
WITH e, value
UNWIND value.text_unit_ids AS text_unit
MATCH (c:__Chunk__ {id:text_unit})
MERGE (e)-[:APPEARS_IN_CHUNK]->(c)
WITH e, value
UNWIND value.document_ids AS document_id
MERGE (d:__Document__ {id:document_id})
MERGE (e)-[:APPEARS_IN_DOCUMENT]->(d)
WITH e, value
UNWIND value.community_ids AS community_id
MERGE (comm:__Community__ {community:community_id})
MERGE (e)-[:BELONGS_TO_COMMUNITY]->(comm)
"""

# class Triple(BaseModel):
#     """A relationship between two entities. This is a generic relationship, and can be used to represent any type of relationship between any two entities."""

#     id: str

#     subject: str | None = None
#     """The source entity name."""

#     predicate: str | None = None
#     """A description of the relationship (optional)."""

#     object: str | None = None
#     """The target entity name."""

#     subject_id: str | None = None
#     """The source entity id."""

#     object_id: str | None = None
#     """The target entity ids."""

#     weight: float | None = 1.0
#     """The edge weight."""

#     description: str | None = None
#     """A description of the relationship (optional)."""

#     predicate_embedding: list[float] | None = None
#     """The semantic embedding for the relationship description (optional)."""

#     text_unit_ids: list[str] | None = None
#     """List of text unit IDs in which the relationship appears (optional)."""

#     document_ids: list[str] | None = None
#     """List of document IDs in which the relationship appears (optional)."""

#     attributes: dict[str, Any] | None = None
#     """Additional attributes associated with the relationship (optional). To be included in the search prompt"""


GET_TRIPLES_QUERY = """
MATCH (e1)-[rel]->(e2)
RETURN e1, rel, e2
"""

PUT_TRIPLES_QUERY = """
MATCH (source:__Entity__ {name: value.subject})
MATCH (target:__Entity__ {name: value.object})
WITH source, target, value
CALL apoc.merge.relationship(source, value.predicate, {}, {}, target) YIELD rel
SET rel += value {.weight, .description, .subject_id, .object_id, .attributes, .text_unit_ids, .document_ids}
WITH rel, value
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
MATCH (c:__Community__)
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