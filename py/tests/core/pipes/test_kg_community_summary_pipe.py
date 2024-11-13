import random
import uuid

import pytest

from core.base import (
    AsyncPipe,
    Community,
    Community,
    Entity,
    KGExtraction,
    Relationship,
)
from core.pipes.kg.community_summary import KGCommunitySummaryPipe
from shared.abstractions.vector import VectorQuantizationType


@pytest.fixture(scope="function")
def kg_pipeline_config():
    return AsyncPipe.PipeConfig(name="kg_community_summary_pipe")


@pytest.fixture(scope="function")
def kg_community_summary_pipe(
    postgres_db_provider,
    litellm_completion_provider,
    litellm_provider,
    kg_pipeline_config,
    local_logging_provider,
):
    return KGCommunitySummaryPipe(
        postgres_db_provider,
        litellm_completion_provider,
        litellm_provider,
        kg_pipeline_config,
        logging_provider=local_logging_provider,
    )


@pytest.fixture(scope="function")
def max_summary_input_length():
    return 65536


@pytest.fixture(scope="function")
def collection_id():
    return uuid.UUID("122fdf6a-e116-546b-a8f6-e4cb2e2c0a09")


@pytest.fixture(scope="function")
def document_id():
    return uuid.UUID("9fbe403b-c11c-5aae-8ade-ef22980c3ad1")


@pytest.fixture(scope="function")
def extraction_ids():
    return [
        uuid.UUID("32ff6daf-6e67-44fa-b2a9-19384f5d9d19"),
        uuid.UUID("42ff6daf-6e67-44fa-b2a9-19384f5d9d19"),
    ]


@pytest.fixture(scope="function")
def embedding_dimension():
    return 512


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
def entities_raw_list(document_id, extraction_ids):
    return [
        Entity(
            name="Entity1",
            description="Description1",
            category="Category1",
            extraction_ids=extraction_ids,
            document_id=document_id,
            attributes={"attr1": "value1", "attr2": "value2"},
        ),
        Entity(
            name="Entity2",
            description="Description2",
            category="Category2",
            extraction_ids=extraction_ids,
            document_id=document_id,
            attributes={"attr3": "value3", "attr4": "value4"},
        ),
    ]


@pytest.fixture(scope="function")
def entities_list(extraction_ids, document_id, embedding_vectors):
    return [
        Entity(
            id=1,
            name="Entity1",
            description="Description1",
            extraction_ids=extraction_ids,
            document_id=document_id,
            description_embedding=embedding_vectors[0],
        ),
        Entity(
            id=2,
            name="Entity2",
            description="Description2",
            extraction_ids=extraction_ids,
            document_id=document_id,
            description_embedding=embedding_vectors[1],
        ),
    ]


@pytest.fixture(scope="function")
def relationships_raw_list(embedding_vectors, extraction_ids, document_id):
    return [
        Relationship(
            id=1,
            subject="Entity1",
            predicate="predicate1",
            object="object1",
            weight=1.0,
            description="description1",
            embedding=embedding_vectors[0],
            extraction_ids=extraction_ids,
            document_id=document_id,
            attributes={"attr1": "value1", "attr2": "value2"},
        ),
        Relationship(
            id=2,
            subject="Entity2",
            predicate="predicate2",
            object="object2",
            weight=1.0,
            description="description2",
            embedding=embedding_vectors[1],
            extraction_ids=extraction_ids,
            document_id=document_id,
            attributes={"attr3": "value3", "attr4": "value4"},
        ),
    ]


@pytest.mark.asyncio
async def test_community_summary_prompt(
    kg_community_summary_pipe,
    entities_list,
    relationships_raw_list,
    max_summary_input_length,
):
    summary = await kg_community_summary_pipe.community_summary_prompt(
        entities_list, relationships_raw_list, max_summary_input_length
    )
    expected_summary = """
            Entity: Entity1
            Descriptions:
                1,Description1
            Relationships:
                1,Entity1,object1,predicate1,description1

            Entity: Entity2
            Descriptions:
                2,Description2
            Relationships:
                2,Entity2,object2,predicate2,description2
    """
    # "\n            Entity: Entity1\n            Descriptions: \n                1,Description1\n            Relationships: \n                1,Entity1,object1,predicate1,description1\n            \n            Entity: Entity2\n            Descriptions: \n                2,Description2\n            Relationships: \n                2,Entity2,object2,predicate2,description2\n            "
    assert summary.strip() == expected_summary.strip()
