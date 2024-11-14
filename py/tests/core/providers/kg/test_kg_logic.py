# tests/core/providers/kg/test_kg_logic.py
import random
import uuid

import pytest

from core.base import (
    Community,
    Community,
    Entity,
    KGExtraction,
    Relationship,
)
from shared.abstractions.vector import VectorQuantizationType


@pytest.fixture(scope="function")
def collection_id():
    return uuid.UUID("122fdf6a-e116-546b-a8f6-e4cb2e2c0a09")


@pytest.fixture(scope="function")
def document_id():
    return uuid.UUID("9fbe403b-c11c-5aae-8ade-ef22980c3ad1")


@pytest.fixture(scope="function")
def chunk_ids():
    return [
        uuid.UUID("32ff6daf-6e67-44fa-b2a9-19384f5d9d19"),
        uuid.UUID("42ff6daf-6e67-44fa-b2a9-19384f5d9d19"),
    ]


@pytest.fixture(scope="function")
def embedding_dimension():
    return 128


@pytest.fixture(scope="function")
def vector_quantization_type():
    return VectorQuantizationType.FP32


@pytest.fixture(scope="function")
def embedding_vectors(embedding_dimension):
    random.seed(42)
    return [
        [random.random() for _ in range(embedding_dimension)] for _ in range(2)
    ]


@pytest.fixture(scope="function")
def entities_raw_list(document_id, chunk_ids):
    return [
        Entity(
            name="Entity1",
            description="Description1",
            category="Category1",
            chunk_ids=chunk_ids,
            document_id=document_id,
            attributes={"attr1": "value1", "attr2": "value2"},
        ),
        Entity(
            name="Entity2",
            description="Description2",
            category="Category2",
            chunk_ids=chunk_ids,
            document_id=document_id,
            attributes={"attr3": "value3", "attr4": "value4"},
        ),
    ]


@pytest.fixture(scope="function")
def entities_list(chunk_ids, document_id, embedding_vectors):
    return [
        Entity(
            name="Entity1",
            description="Description1",
            chunk_ids=chunk_ids,
            document_id=document_id,
            description_embedding=embedding_vectors[0],
        ),
        Entity(
            name="Entity2",
            description="Description2",
            chunk_ids=chunk_ids,
            document_id=document_id,
            description_embedding=embedding_vectors[1],
        ),
    ]


@pytest.fixture(scope="function")
def relationships_raw_list(embedding_vectors, chunk_ids, document_id):
    return [
        Relationship(
            subject="Entity1",
            predicate="predicate1",
            object="object1",
            weight=1.0,
            description="description1",
            embedding=embedding_vectors[0],
            chunk_ids=chunk_ids,
            document_id=document_id,
            attributes={"attr1": "value1", "attr2": "value2"},
        ),
        Relationship(
            subject="Entity2",
            predicate="predicate2",
            object="object2",
            weight=1.0,
            description="description2",
            embedding=embedding_vectors[1],
            chunk_ids=chunk_ids,
            document_id=document_id,
            attributes={"attr3": "value3", "attr4": "value4"},
        ),
    ]


@pytest.fixture(scope="function")
def communities_list(entities_list, relationships_raw_list):
    return [
        Community(
            name="Community1",
            description="Description1",
            entities=[entities_list[0]],
            relationships=[relationships_raw_list[0]],
        ),
        Community(
            name="Community2",
            description="Description2",
            entities=[entities_list[1]],
            relationships=[relationships_raw_list[1]],
        ),
    ]


@pytest.fixture(scope="function")
def community_table_info(collection_id):
    return [
        ("Entity1", 1, None, 0, False, [1, 2], collection_id),
        ("Entity2", 2, None, 0, False, [1, 2], collection_id),
    ]


@pytest.fixture(scope="function")
def kg_extractions(
    chunk_ids, entities_raw_list, relationships_raw_list, document_id
):
    return [
        KGExtraction(
            chunk_ids=chunk_ids,
            entities=entities_raw_list,
            relationships=relationships_raw_list,
            document_id=document_id,
        )
    ]


@pytest.fixture(scope="function")
def community_list(embedding_vectors, collection_id):
    return [
        Community(
            community_number=1,
            level=0,
            collection_id=collection_id,
            name="Community Report 1",
            summary="Summary of the community report",
            rating=8.0,
            rating_explanation="Rating explanation of the community report",
            findings=["Findings of the community report"],
            embedding=embedding_vectors[0],
        ),
        Community(
            community_number=2,
            level=0,
            collection_id=collection_id,
            name="Community Report",
            summary="Summary of the community report",
            rating=8.0,
            rating_explanation="Rating explanation of the community report",
            findings=["Findings of the community report"],
            embedding=embedding_vectors[1],
        ),
    ]


@pytest.mark.asyncio
async def test_create_tables(
    postgres_db_provider,
    collection_id,
    embedding_dimension,
    vector_quantization_type,
):
    assert await postgres_db_provider.get_entities(collection_id) == {
        "entities": [],
        "total_entries": 0,
    }
    assert await postgres_db_provider.get_relationships(collection_id) == {
        "relationships": [],
        "total_entries": 0,
    }
    assert await postgres_db_provider.get_communities(collection_id) == {
        "communities": [],
        "total_entries": 0,
    }


@pytest.mark.asyncio
async def test_add_entities_raw(
    postgres_db_provider, entities_raw_list, collection_id
):
    await postgres_db_provider.add_entities(
        entities_raw_list, table_name="chunk_entity"
    )
    entities = await postgres_db_provider.get_entities(
        collection_id, entity_table_name="chunk_entity"
    )
    assert entities["entities"][0].name == "Entity1"
    assert entities["entities"][1].name == "Entity2"
    assert len(entities["entities"]) == 2
    assert entities["total_entries"] == 2


@pytest.mark.asyncio
async def test_add_entities(
    postgres_db_provider, entities_list, collection_id
):
    await postgres_db_provider.add_entities(
        entities_list, table_name="document_entity"
    )
    entities = await postgres_db_provider.get_entities(
        collection_id, entity_table_name="document_entity"
    )
    assert entities["entities"][0].name == "Entity1"
    assert entities["entities"][1].name == "Entity2"
    assert len(entities["entities"]) == 2
    assert entities["total_entries"] == 2


@pytest.mark.asyncio
async def test_add_relationships(
    postgres_db_provider, relationships_raw_list, collection_id
):
    await postgres_db_provider.add_relationships(
        relationships_raw_list, table_name="chunk_relationship"
    )
    relationships = await postgres_db_provider.get_relationships(collection_id)
    assert relationships["relationships"][0].subject == "Entity1"
    assert relationships["relationships"][1].subject == "Entity2"
    assert len(relationships["relationships"]) == 2
    assert relationships["total_entries"] == 2

@pytest.mark.asyncio
async def test_get_entity_map(
    postgres_db_provider,
    entities_raw_list,
    relationships_raw_list,
    document_id,
):
    await postgres_db_provider.add_entities(
        entities_raw_list, table_name="chunk_entity"
    )
    entity_map = await postgres_db_provider.get_entity_map(0, 2, document_id)
    assert entity_map["Entity1"]["entities"][0].name == "Entity1"
    assert entity_map["Entity2"]["entities"][0].name == "Entity2"

    await postgres_db_provider.add_relationships(relationships_raw_list)
    entity_map = await postgres_db_provider.get_entity_map(0, 2, document_id)
    assert entity_map["Entity1"]["entities"][0].name == "Entity1"
    assert entity_map["Entity2"]["entities"][0].name == "Entity2"

    assert entity_map["Entity1"]["relationships"][0].subject == "Entity1"
    assert entity_map["Entity2"]["relationships"][0].subject == "Entity2"


@pytest.mark.asyncio
async def test_upsert_embeddings(
    postgres_db_provider, collection_id, entities_list
):
    table_name = "document_entity"

    entities_list_to_upsert = [
        (
            entity.name,
            entity.description,
            str(entity.description_embedding),
            entity.chunk_ids,
            entity.document_id,
        )
        for entity in entities_list
    ]

    await postgres_db_provider.add_entities(
        entities_list_to_upsert, table_name
    )

    entities = await postgres_db_provider.get_entities(
        collection_id, entity_table_name=table_name
    )
    assert entities["entities"][0].name == "Entity1"
    assert entities["entities"][1].name == "Entity2"


@pytest.mark.asyncio
async def test_get_all_relationships(
    postgres_db_provider, collection_id, relationships_raw_list
):
    await postgres_db_provider.add_relationships(relationships_raw_list)
    relationships = await postgres_db_provider.get_relationships(collection_id)
    assert relationships["relationships"][0].subject == "Entity1"
    assert relationships["relationships"][1].subject == "Entity2"
    assert len(relationships["relationships"]) == 2


@pytest.mark.asyncio
async def test_get_communities(
    postgres_db_provider, collection_id, community_list
):
    await postgres_db_provider.add_community(community_list[0])
    await postgres_db_provider.add_community(community_list[1])
    communities = await postgres_db_provider.get_communities(collection_id)
    assert communities["communities"][0].name == "Community Report 1"
    assert len(communities["communities"]) == 2
    assert communities["total_entries"] == 2


@pytest.fixture(scope="function")
def leiden_params_1():
    return {
        "resolution": 1.0,
        "max_cluster_size": 1000,
        "random_seed": 42,
    }


@pytest.mark.asyncio
async def test_perform_graph_clustering(
    postgres_db_provider,
    collection_id,
    leiden_params_1,
    entities_list,
    relationships_raw_list,
):

    # addd entities and relationships
    await postgres_db_provider.add_entities(
        entities_list, table_name="document_entity"
    )
    await postgres_db_provider.add_relationships(
        relationships_raw_list, table_name="chunk_relationship"
    )

    num_communities = await postgres_db_provider.perform_graph_clustering(
        collection_id, leiden_params_1
    )
    assert num_communities


@pytest.mark.asyncio
async def test_get_community_details(
    postgres_db_provider,
    entities_list,
    relationships_raw_list,
    collection_id,
    community_list,
    community_table_info,
):

    await postgres_db_provider.add_entities(
        entities_list, table_name="document_entity"
    )
    await postgres_db_provider.add_relationships(
        relationships_raw_list, table_name="chunk_relationship"
    )
    await postgres_db_provider.add_community_info(community_table_info)
    await postgres_db_provider.add_community(community_list[0])

    community_level, entities, relationships = (
        await postgres_db_provider.get_community_details(
            community_number=1, collection_id=collection_id
        )
    )

    assert community_level == 0
    # TODO: change these to objects
    assert entities[0].name == "Entity1"
    assert relationships[0].subject == "Entity1"
