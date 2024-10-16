# tests/core/providers/kg/test_kg_logic.py
import pytest
import random
import uuid
from core.providers.kg.postgres import PostgresKGProvider
from core.base import Entity, Triple, Community, CommunityReport, KGExtraction
from shared.abstractions.vector import VectorQuantizationType

@pytest.fixture(scope="function")
def collection_id():
    return uuid.UUID('122fdf6a-e116-546b-a8f6-e4cb2e2c0a09')

@pytest.fixture(scope="function")
def document_id():
    return uuid.UUID('9fbe403b-c11c-5aae-8ade-ef22980c3ad1')

@pytest.fixture(scope="function")
def extraction_ids():
    return [uuid.UUID('32ff6daf-6e67-44fa-b2a9-19384f5d9d19'), uuid.UUID('42ff6daf-6e67-44fa-b2a9-19384f5d9d19')]

@pytest.fixture(scope="function")
def embedding_dimension():
    return 512

@pytest.fixture(scope="function")
def vector_quantization_type():
    return VectorQuantizationType.FP32

@pytest.fixture(scope="function")
def embedding_vectors(embedding_dimension):
    random.seed(42)
    return [[random.random() for _ in range(embedding_dimension)] for _ in range(2)]

@pytest.fixture(scope="function")
def entities_raw_list(document_id, extraction_ids):
    return [
        Entity(name="Entity1", description="Description1", category="Category1", extraction_ids=extraction_ids, document_id=document_id, attributes={"attr1": "value1", "attr2": "value2"}),
        Entity(name="Entity2", description="Description2", category="Category2", extraction_ids=extraction_ids, document_id=document_id, attributes={"attr3": "value3", "attr4": "value4"}),
    ]

@pytest.fixture(scope="function")
def entities_list(extraction_ids, document_id, embedding_vectors):
    return [
        Entity(name="Entity1", description="Description1", extraction_ids=extraction_ids, document_id=document_id, description_embedding=embedding_vectors[0]),
        Entity(name="Entity2", description="Description2", extraction_ids=extraction_ids, document_id=document_id, description_embedding=embedding_vectors[1]),
    ]

@pytest.fixture(scope="function")
def triples_raw_list(embedding_vectors, extraction_ids, document_id):
    return [
        Triple(subject="Entity1", predicate="predicate1", object="object1", weight=1.0, description="description1", embedding=embedding_vectors[0], extraction_ids=extraction_ids, document_id=document_id, attributes={"attr1": "value1", "attr2": "value2"}),
        Triple(subject="Entity2", predicate="predicate2", object="object2", weight=1.0, description="description2", embedding=embedding_vectors[1], extraction_ids=extraction_ids, document_id=document_id, attributes={"attr3": "value3", "attr4": "value4"}),
    ]

@pytest.fixture(scope="function")
def communities_list(entities_list, triples_raw_list):
    return [
        Community(name="Community1", description="Description1", entities=[entities_list[0]], triples=[triples_raw_list[0]]),
        Community(name="Community2", description="Description2", entities=[entities_list[1]], triples=[triples_raw_list[1]]),
    ]

@pytest.fixture(scope="function")
def kg_extractions(extraction_ids, entities_raw_list, triples_raw_list, document_id):
    return [KGExtraction(extraction_ids=extraction_ids, entities=entities_raw_list, triples=triples_raw_list, document_id=document_id)]

@pytest.fixture(scope="function")
def community_report_list(embedding_vectors):
    return [
        CommunityReport(
            title="Community Report 1",
            summary="Summary of the community report",
            findings="Findings of the community report",
            rank=1.0,
            summary_embedding=embedding_vectors[0],
        ),
        CommunityReport(
            title="Community Report",
            summary="Summary of the community report",
            findings="Findings of the community report",
            rank=1.0,
            summary_embedding=embedding_vectors[1],
        ),
    ]


@pytest.mark.asyncio
async def test_kg_provider_initialization(postgres_kg_provider):
    assert isinstance(postgres_kg_provider, PostgresKGProvider)

@pytest.mark.asyncio
async def test_create_tables(postgres_kg_provider, collection_id, embedding_dimension, vector_quantization_type):
    assert await postgres_kg_provider.get_entities(collection_id) == {'entities': [], "total_entries": 0}
    assert await postgres_kg_provider.get_triples(collection_id) == {'triples': [], "total_entries": 0}
    assert await postgres_kg_provider.get_communities(collection_id) == {'communities': [], "total_entries": 0}

@pytest.mark.asyncio
async def test_add_entities_raw(postgres_kg_provider, entities_raw_list, collection_id):
    await postgres_kg_provider.add_entities(entities_raw_list, table_name='entity_raw')
    entities = await postgres_kg_provider.get_entities(collection_id, entity_table_name='entity_raw')
    assert entities["entities"][0].name == "Entity1"
    assert entities["entities"][1].name == "Entity2"
    assert len(entities["entities"]) == 2
    assert entities["total_entries"] == 2

@pytest.mark.asyncio   
async def test_add_entities(postgres_kg_provider, entities_list, collection_id):    
    await postgres_kg_provider.add_entities(entities_list, table_name='entity_embedding')
    entities = await postgres_kg_provider.get_entities(collection_id, entity_table_name='entity_embedding')
    assert entities["entities"][0].name == "Entity1"
    assert entities["entities"][1].name == "Entity2"
    assert len(entities["entities"]) == 2
    assert entities["total_entries"] == 2

@pytest.mark.asyncio
async def test_add_triples(postgres_kg_provider, triples_raw_list, collection_id):
    await postgres_kg_provider.add_triples(triples_raw_list, table_name='triple_raw')
    triples = await postgres_kg_provider.get_triples(collection_id)
    assert triples["triples"][0].subject == "Entity1"
    assert triples["triples"][1].subject == "Entity2"
    assert len(triples["triples"]) == 2
    assert triples["total_entries"] == 2


@pytest.mark.asyncio
async def test_add_kg_extractions(postgres_kg_provider, kg_extractions, collection_id):
    added_extractions = await postgres_kg_provider.add_kg_extractions(kg_extractions, table_suffix='_raw')

    assert added_extractions == (2, 2)

    entities = await postgres_kg_provider.get_entities(collection_id)
    assert entities["entities"][0].name == "Entity1"
    assert entities["entities"][1].name == "Entity2"
    assert len(entities["entities"]) == 2
    assert entities["total_entries"] == 2

    triples = await postgres_kg_provider.get_triples(collection_id)
    assert triples["triples"][0].subject == "Entity1"   
    assert triples["triples"][1].subject == "Entity2"
    assert len(triples["triples"]) == 2
    assert triples["total_entries"] == 2

# @pytest.mark.asyncio
# async def test_get_entity_map(postgres_kg_provider, entities_list, document_id):
#     await postgres_kg_provider.add_entities(entities_list, table_name='entity_raw')
#     entity_map = await postgres_kg_provider.get_entity_map(0, 10, document_id)
#     assert entity_map["entities"][0].name == "Entity1"
#     assert entity_map["entities"][1].name == "Entity2"
#     assert len(entity_map["entities"]) == 2
#     assert entity_map["total_entries"] == 2


# @pytest.mark.asyncio
# async def test_add_communities(postgres_kg_provider):
#     await postgres_kg_provider.add_communities([Community(name="Community1"), Community(name="Community2")])

# @pytest.mark.asyncio
# async def test_add_community_reports(postgres_kg_provider):
#     await postgres_kg_provider.add_community_reports([CommunityReport(title="Community Report 1"), CommunityReport(title="Community Report 2")])


