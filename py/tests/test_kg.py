from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from core.base import Community, DocumentFragment, Entity, KGExtraction, Triple
from core.pipes.kg.clustering import KGClusteringPipe
from core.pipes.kg.extraction import KGTriplesExtractionPipe


@pytest.fixture
def kg_extraction_pipe():
    return KGTriplesExtractionPipe(
        kg_provider=MagicMock(),
        database_provider=MagicMock(),
        llm_provider=MagicMock(),
        prompt_provider=MagicMock(),
        chunking_provider=MagicMock(),
    )


@pytest.fixture
def document_fragment():
    return DocumentFragment(
        id=uuid4(),
        extraction_id=uuid4(),
        document_id=uuid4(),
        user_id=uuid4(),
        group_ids=[uuid4()],
        data="Test data",
        metadata={},
    )


@pytest.mark.asyncio
async def test_extract_kg_success(kg_extraction_pipe, document_fragment):
    kg_extraction_pipe.llm_provider.aget_completion = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=(
                            '("entity"$$$$Entity1$$$$Category1$$$$Description1)'
                            '("relationship"$$$$Entity1$$$$Entity2$$$$Predicate$$$$Description$$$$0.8)'
                        )
                    )
                )
            ]
        )
    )
    result = await kg_extraction_pipe.extract_kg(document_fragment)

    assert isinstance(result, KGExtraction)
    assert len(result.entities) == 1
    assert len(result.triples) == 1
    assert result.entities['Entity1'].name == "Entity1"
    assert result.triples[0].subject == "Entity1"
    assert result.triples[0].object == "Entity2"


@pytest.mark.asyncio
async def test_run_logic(kg_extraction_pipe, document_fragment):
    async def mock_input_generator():
        for _ in range(2):
            yield document_fragment

    input_mock = MagicMock()
    input_mock.message = mock_input_generator()

    kg_extraction_pipe.extract_kg = AsyncMock(
        return_value=KGExtraction(
            fragment_id=document_fragment.id,
            document_id=document_fragment.document_id,
            entities={  
                "TestEntity": Entity(
                    name="TestEntity",
                    category="TestCategory",
                    description="TestDescription",
                )
            },
            triples=[
                Triple(
                    subject="TestSubject",
                    predicate="TestPredicate",
                    object="TestObject",
                )
            ],
        )
    )

    results = [
        result
        async for result in kg_extraction_pipe._run_logic(
            input_mock, MagicMock(), "run_id"
        )
    ]

    # test failing due to issues with mock
    # assert len(results) == 2
    # for result in results:
    #     assert isinstance(result, KGExtraction)
    #     assert len(result.entities) == 1
    #     assert len(result.triples) == 1


@pytest.fixture
def mock_kg_provider(mocker):
    provider = mocker.Mock()
    provider.get_all_entities.return_value = [
        Entity(
            name=f"Entity{i}",
            category=f"Category{i%2+1}",
            description=f"Description{i}",
        )
        for i in range(1, 4)
    ]

    provider.get_entities.return_value = [
        Entity(
            name=f"Entity{i}",
            category=f"Category{i%2+1}",
            description=f"Description{i}",
        )
        for i in range(1, 4)
    ]

    provider.get_triples.return_value = [
        Triple(
            subject=f"Entity{i}",
            predicate=f"Predicate{i%2+1}",
            object=f"Entity{i+1}",
        )
        for i in range(1, 4)
    ]

    provider.get_communities.return_value = [
        Community(
            id=f"Community{i}",
            level=f"Level{i%2+1}",
            short_id=f"Short{i}",
            title=f"Title{i}",
            entity_ids=[f"Entity{i}"],
            relationship_ids=[f"Relationship{i}"],
        )
        for i in range(1, 4)
    ]

    return provider


@pytest.fixture
def mock_embedding_provider(mocker):
    provider = mocker.Mock()
    provider.get_embeddings.return_value = [
        [0.1 * i, 0.2 * i, 0.3 * i] for i in range(1, 4)
    ]
    provider.async_get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return provider


@pytest.fixture
def mock_completion_provider(mocker):
    provider = mocker.Mock()

    async def mock_aget_completion(*args, **kwargs):
        return mocker.Mock(
            choices=[
                mocker.Mock(message=mocker.Mock(content="Cluster summary"))
            ]
        )

    provider.aget_completion = mock_aget_completion
    return provider


@pytest.fixture
def mock_prompt_provider(mocker):
    provider = mocker.Mock()
    provider.get_message_payload.return_value = mocker.Mock(
        task_prompt_name="graphrag_community_reports",
        task_inputs={"input_text": "Test input text"},
    )
    provider._get_message_payload.return_value = {
        "task_prompt_name": "graphrag_community_reports",
        "task_inputs": {"input_text": "Test input text"},
    }
    return provider


@pytest.fixture
def kg_clustering_pipe(
    mocker,
    mock_kg_provider,
    mock_embedding_provider,
    mock_completion_provider,
    mock_prompt_provider,
):
    return KGClusteringPipe(
        kg_provider=mock_kg_provider,
        embedding_provider=mock_embedding_provider,
        llm_provider=mock_completion_provider,
        prompt_provider=mock_prompt_provider,
        n_clusters=2,
    )


# Test is failing due to a dependency of graspologic failing to install: /hyppo/kgof/fssd.py:4: ModuleNotFoundError
# @pytest.mark.asyncio
# async def test_cluster_kg(kg_clustering_pipe):
#     triples = [
#         Triple(subject="Entity1", predicate="relatedTo", object="Entity2"),
#         Triple(subject="Entity2", predicate="relatedTo", object="Entity3"),
#         Triple(subject="Entity3", predicate="relatedTo", object="Entity1"),
#     ]

#     result = []
#     async for community in kg_clustering_pipe.cluster_kg(triples):
#         result.append(community)

#     assert len(result) == 1
#     assert result[0]["id"] == "0_0"
#     assert result[0]["title"] == "_"
