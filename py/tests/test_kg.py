# import json
# import uuid
# from unittest.mock import Mock, patch

# import pytest

# from r2r_core.base.abstractions.document import DocumentFragment
# from r2r_core.base.abstractions.graph import Entity, Triple
# from r2r_core.base.providers.kg import KGConfig
# from r2r_core.providers.kg.neo4j.provider import Neo4jKGProvider


# @pytest.fixture
# def neo4j_kg_provider():
#     extra_fields = {
#         "user": "neo4j",
#         "password": "ineedastrongerpassword",
#         "url": "bolt://localhost:7688",
#         "database": "neo4j",
#     }
#     config = KGConfig(provider="neo4j", extra_fields=extra_fields)
#     return Neo4jKGProvider(config)


# @pytest.fixture(autouse=True)
# def clean_graph(neo4j_kg_provider):
#     neo4j_kg_provider.delete_all_nodes()
#     yield
#     neo4j_kg_provider.delete_all_nodes()


# def get_uuid():
#     return str(uuid.uuid4())


# @pytest.fixture
# def test_chunks():
#     return [
#         DocumentFragment(
#             id=get_uuid(),
#             data="Test chunk 1",
#             metadata={"testkey": "testvalue"},
#             document_id=get_uuid(),
#             extraction_id=get_uuid(),
#         ),
#         DocumentFragment(
#             id=get_uuid(),
#             data="Test chunk 2",
#             metadata={"testkey": "testvalue"},
#             document_id=get_uuid(),
#             extraction_id=get_uuid(),
#         ),
#     ]


# @pytest.fixture
# def test_entities():
#     return [
#         Entity(
#             id=get_uuid(),
#             category="Test category 1",
#             subcategory=None,
#             value="Test entity 1",
#             description="Test entity 1 description",
#             description_embedding=[1.0, 2.0, 3.0],
#             name_embedding=[1.0, 2.0, 3.0],
#             graph_embedding=[1.0, 2.0, 3.0],
#             community_ids=[get_uuid()],
#             text_unit_ids=[get_uuid()],
#             document_ids=[get_uuid(), get_uuid()],
#             rank=1,
#             attributes={"testkey": "testvalue"},
#         ),
#         # Entity(id=get_uuid(), category="Test category 2", subcategory=None, value="Test entity 2", description="Test entity 2 description", description_embedding=[1.0, 2.0, 3.0], name_embedding=[1.0, 2.0, 3.0], graph_embedding=[1.0, 2.0, 3.0], community_ids=[get_uuid()], text_unit_ids=[get_uuid()], document_ids=[get_uuid(), get_uuid()], rank=1, attributes={"testkey": "testvalue"})
#     ]


# @pytest.fixture
# def test_triples():
#     return [
#         Triple(
#             id=get_uuid(),
#             subject=get_uuid(),
#             predicate="test_predicate",
#             object=get_uuid(),
#             weight=1.0,
#             description="Test triple description",
#             predicate_embedding=[1.0, 2.0, 3.0],
#             text_unit_ids=[get_uuid()],
#             document_ids=[get_uuid()],
#             attributes={"testkey": "testvalue"},
#         )
#     ]


# def test_upsert_chunks(neo4j_kg_provider, test_chunks, clean_graph):
#     neo4j_kg_provider.upsert_chunks(test_chunks)
#     neo4j_output = neo4j_kg_provider.get_chunks()
#     chunks = [record["c"]._properties for record in neo4j_output.records]
#     assert len(chunks) == len(test_chunks)
#     for chunk, test_chunk in zip(chunks, test_chunks):
#         assert chunk["id"] == str(test_chunk.id)
#         assert chunk["data"] == test_chunk.data
#         assert json.loads(chunk["metadata"]) == test_chunk.metadata
#         assert chunk["document_id"] == str(test_chunk.document_id)
#         assert chunk["extraction_id"] == str(test_chunk.extraction_id)


# def test_upsert_entities(neo4j_kg_provider, test_entities):
#     neo4j_kg_provider.upsert_entities(test_entities)
#     neo4j_output = neo4j_kg_provider.get_entities()
#     entities = [record["e"]._properties for record in neo4j_output.records]
#     assert len(entities) == len(test_entities)
#     for entity, test_entity in zip(entities, test_entities):
#         assert entity["id"] == test_entity.id
#         assert entity["category"] == test_entity.category
#         assert entity["value"] == test_entity.value
#         assert entity["description"] == test_entity.description


# def test_upsert_triples(neo4j_kg_provider, test_triples):
#     triples_count = neo4j_kg_provider.upsert_triples(test_triples)
#     triples = neo4j_kg_provider.get_triples()
#     assert len(triples) == len(test_triples)
#     for triple, test_triple in zip(triples, test_triples):
#         assert triple.id == test_triple.id
#         assert triple.subject == test_triple.subject
#         assert triple.predicate == test_triple.predicate
#         assert triple.object == test_triple.object


# def test_upsert_communities(neo4j_kg_provider, test_communities):
#     neo4j_kg_provider.upsert_communities(test_communities)
#     neo4j_output = neo4j_kg_provider.get_communities()
#     communities = [record["c"]._properties for record in neo4j_output.records]
#     assert len(communities) == len(test_communities)
#     for community, test_community in zip(communities, test_communities):
#         assert community["id"] == test_community.id
#         assert community["name"] == test_community.name
