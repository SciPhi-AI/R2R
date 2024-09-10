UNIQUE_CONSTRAINTS = [
    # "create constraint on (c:__Chunk__) assert c.id is unique;",
    # "create constraint on (d:__Document__) assert d.id is unique;",
    # "create constraint on (c:__Community__) assert c.community is unique;",
    # "create constraint on (e:__Entity__) assert e.id is unique;",
    # "create constraint on (e:__Entity__) assert e.name is unique;",
    # "create constraint on (e:__Covariate__) assert e.title is unique;",
    # "create constraint on ()-[rel:RELATED]->() assert rel.id is unique;" # memgraph does not support this
]

GET_CHUNKS_QUERY = """
MATCH (c:__Chunk__)
RETURN c
"""

# class DocumentFragment(BaseModel):
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

# searching by entity_name
GET_ENTITIES_QUERY = """
MATCH (e:__Entity__)
WHERE size($entity_ids) = 0 OR e.name IN $entity_ids
RETURN e
"""

PUT_ENTITIES_QUERY = """
WITH value, [toUpper(substring(value.category, 0, 1)) + substring(value.category, 1)] AS upperCamelCategory
CALL{
    WITH value, upperCamelCategory
    CALL merge.node(upperCamelCategory, {name: value.name}, {}, {}) YIELD node RETURN node
}
WITH value, node
SET node.description = CASE
    WHEN node.description IS NULL THEN value.description
    ELSE node.description + '\n\n' + value.description
END,
node.rank = CASE
    WHEN node.rank IS NULL THEN value.rank
    ELSE CASE WHEN value.rank > node.rank THEN value.rank ELSE node.rank END
END,
node.attributes = CASE
    WHEN node.attributes IS NULL THEN value.attributes
    ELSE node.attributes + '\n\n' + value.attributes
END
WITH node as e, value
UNWIND value.text_unit_ids AS text_unit
MATCH (c:__Chunk__ {id:text_unit})
MERGE (e)-[:APPEARS_IN_CHUNK]->(c)
WITH e, value
UNWIND value.document_ids AS document_id
MATCH (d:__Document__ {id:document_id})
MERGE (e)-[:APPEARS_IN_DOCUMENT]->(d)
WITH e, value
UNWIND value.community_ids AS community_id
MATCH (comm:__Community__ {community:community_id})
MERGE (e)-[:BELONGS_TO_COMMUNITY]->(comm)
"""

# use this after PUT_ENTITIES_QUERY when you have embeddings.
PUT_ENTITIES_EMBEDDINGS_QUERY = """
MATCH (e:__Entity__ {name: value.name})
SET e += value {.description}
WITH e, value
SET e.name_embedding = value.name_embedding
SET e.description_embedding = value.description_embedding
"""

## get triples by subject and object
GET_TRIPLES_QUERY = """
    MATCH (e1)-[rel]->(e2)
    RETURN e1, rel, e2
"""

GET_TRIPLES_BY_SUBJECT_AND_OBJECT_QUERY = """
UNWIND $triples AS triple
    MATCH (e1:__Entity__)-[rel]->(e2:__Entity__)
    WHERE e1.name = triple.subject
      AND e2.name = triple.object
      AND type(rel) = triple.predicate
    RETURN e1, rel, e2
"""

PUT_TRIPLES_QUERY = """
WITH value, toUpper(value.predicate) AS upperCamelPredicate
MATCH (source:__Entity__ {name: value.subject})
MATCH (target:__Entity__ {name: value.object})
WITH source, target, value, upperCamelPredicate
CALL {
    WITH source, target, upperCamelPredicate
    CALL merge.relationship(source, upperCamelPredicate, {}, {}, target) YIELD rel RETURN rel
}
WITH rel, value
SET rel.weight = CASE
    WHEN rel.weight IS NULL THEN value.weight
    ELSE CASE WHEN value.weight > rel.weight THEN value.weight ELSE rel.weight END
END,
rel.description = CASE
    WHEN rel.description IS NULL THEN value.description
    ELSE rel.description + '\n\n' + value.description
END,
rel.attributes = CASE
    WHEN rel.attributes IS NULL THEN value.attributes
    ELSE rel.attributes + '\n\n' + value.attributes
END,
rel.text_unit_ids = CASE
    WHEN rel.text_unit_ids IS NULL THEN value.text_unit_ids
    ELSE rel.text_unit_ids + value.text_unit_ids
END,
rel.document_ids = CASE
    WHEN rel.document_ids IS NULL THEN value.document_ids
    ELSE rel.document_ids + value.document_ids
END
WITH rel, value
RETURN count(*) as createdRels
"""

# PUT_TRIPLES_QUERY = """
# WITH value, toUpper(value.predicate) AS upperCamelPredicate
# MATCH (source:__Entity__ {name: value.subject})
# MATCH (target:__Entity__ {name: value.object})
# WITH source, target, value, upperCamelPredicate
# MERGE (source)-[rel:upperCamelPredicate]->(target)
# ON CREATE SET
#     rel.weight = value.weight,
#     rel.description = value.description,
#     rel.attributes = value.attributes,
#     rel.text_unit_ids = value.text_unit_ids,
#     rel.document_ids = value.document_ids
# ON MATCH SET
#     rel.weight = CASE
#         WHEN value.weight > rel.weight THEN value.weight
#         ELSE rel.weight
#     END,
#     rel.description = rel.description + '\n\n' + value.description,
#     rel.attributes = rel.attributes + '\n\n' + value.attributes,
#     rel.text_unit_ids = rel.text_unit_ids + value.text_unit_ids,
#     rel.document_ids = rel.document_ids + value.document_ids
# RETURN count(*) AS createdRels
# """

# MERGE (source)-[rel:upperCamelPredicate]->(target)
# ON CREATE SET
#     rel.weight = value.weight,
#     rel.description = value.description,
#     rel.attributes = value.attributes,
#     rel.text_unit_ids = value.text_unit_ids,
#     rel.document_ids = value.document_ids
# ON MATCH SET
#     rel.weight = CASE
#         WHEN value.weight > rel.weight THEN value.weight
#         ELSE rel.weight
#     END,
#     rel.description = rel.description + '\n\n' + value.description,
#     rel.attributes = rel.attributes + '\n\n' + value.attributes,
#     rel.text_unit_ids = rel.text_unit_ids + value.text_unit_ids,
#     rel.document_ids = rel.document_ids + value.document_ids
# RETURN count(*) AS createdRels

GET_COMMUNITIES_QUERY = """
MATCH (c:__Community__)
WHERE $level IS NULL OR c.level = $level
RETURN c
"""

PUT_COMMUNITIES_QUERY = """
MERGE (c:__Community__ {community:value.id})
SET c += value {.level, .rank, .summary}
WITH c, value
SET c.summary_embedding = value.summary_embedding
RETURN count(*) as createdCommunities
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

# TODO(@antejavor): Figure out alternative, this is not used at the moment
PUT_COVARIATES_QUERY = """
MERGE (c:__Covariate__ {id:value.id})
SET c += apoc.map.clean(value, ["text_unit_id", "document_ids", "n_tokens"], [NULL, ""])
WITH c, value
MATCH (ch:__Chunk__ {id: value.text_unit_id})
MERGE (ch)-[:HAS_COVARIATE]->(c)
"""
