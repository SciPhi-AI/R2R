import uuid

import pytest

from r2r import R2RClient, R2RException


@pytest.fixture(scope="session")
def config():

    class TestConfig:
        base_url = "http://localhost:7272"
        superuser_email = "admin@example.com"
        superuser_password = "change_me_immediately"

    return TestConfig()


@pytest.fixture(scope="session")
def client(config):
    """Create a client instance and possibly log in as a superuser."""
    client = R2RClient(config.base_url)
    client.users.login(config.superuser_email, config.superuser_password)
    return client


@pytest.fixture
def test_collection(client):
    """Create a test collection (and thus a graph) for testing, then delete it
    afterwards."""
    collection_id = client.collections.create(
        name=f"Test Collection {uuid.uuid4()}",
        description="A sample collection for graph tests",
    ).results.id

    yield collection_id
    # Cleanup if needed
    # If there's a deletion endpoint for collections, call it here.
    client.collections.delete(id=collection_id)


def test_list_graphs(client: R2RClient):
    resp = client.graphs.list(limit=5)
    assert resp.results is not None, "No results field in list response"


def test_create_and_get_graph(client: R2RClient, test_collection):
    # `test_collection` fixture creates a collection and returns ID
    collection_id = test_collection
    resp = client.graphs.retrieve(collection_id=collection_id).results
    assert str(resp.collection_id) == str(collection_id), "Graph ID mismatch"


def test_update_graph(client: R2RClient, test_collection):
    collection_id = test_collection
    new_name = "Updated Test Graph Name"
    new_description = "Updated test description"

    resp = client.graphs.update(collection_id=collection_id,
                                name=new_name,
                                description=new_description).results

    assert resp.name == new_name, "Name not updated correctly"
    assert resp.description == new_description, (
        "Description not updated correctly")


def test_list_entities(client: R2RClient, test_collection):
    collection_id = test_collection
    resp = client.graphs.list_entities(collection_id=collection_id,
                                       limit=5).results
    assert isinstance(resp, list), "No results array in entities response"


def test_create_and_get_entity(client: R2RClient, test_collection):
    collection_id = test_collection
    entity_name = "Test Entity"
    entity_description = "Test entity description"

    create_resp = client.graphs.create_entity(
        collection_id=collection_id,
        name=entity_name,
        description=entity_description,
    ).results
    entity_id = str(create_resp.id)

    resp = client.graphs.get_entity(collection_id=collection_id,
                                    entity_id=entity_id).results
    assert resp.name == entity_name, "Entity name mismatch"


def test_list_relationships(client: R2RClient, test_collection):
    collection_id = test_collection
    resp = client.graphs.list_relationships(collection_id=collection_id,
                                            limit=5).results
    assert isinstance(resp, list), "No results array in relationships response"


def test_create_and_get_relationship(client: R2RClient, test_collection):
    collection_id = test_collection

    # Create two entities
    entity1 = client.graphs.create_entity(
        collection_id=collection_id,
        name="Entity 1",
        description="Entity 1 description",
    ).results
    entity2 = client.graphs.create_entity(
        collection_id=collection_id,
        name="Entity 2",
        description="Entity 2 description",
    ).results

    # Create relationship
    rel_resp = client.graphs.create_relationship(
        collection_id=collection_id,
        subject="Entity 1",
        subject_id=entity1.id,
        predicate="related_to",
        object="Entity 2",
        object_id=entity2.id,
        description="Test relationship",
    ).results
    relationship_id = str(rel_resp.id)

    # Get relationship
    resp = client.graphs.get_relationship(
        collection_id=collection_id, relationship_id=relationship_id).results
    assert resp.predicate == "related_to", "Relationship predicate mismatch"


# def test_build_communities(client: R2RClient, test_collection):
#     collection_id = test_collection

#     # Create two entities
#     entity1 = client.graphs.create_entity(
#         collection_id=collection_id,
#         name="Entity 1",
#         description="Entity 1 description",
#     ).results
#     entity2 = client.graphs.create_entity(
#         collection_id=collection_id,
#         name="Entity 2",
#         description="Entity 2 description",
#     ).results

#     # Create relationship
#     rel_resp = client.graphs.create_relationship(
#         collection_id=str(collection_id),
#         subject="Entity 1",
#         subject_id=entity1.id,
#         predicate="related_to",
#         object="Entity 2",
#         object_id=entity2.id,
#         description="Test relationship",
#     ).results
#     relationship_id = str(rel_resp.id)

#     # Build communities
#     resp = client.graphs.build(
#         collection_id=str(collection_id),
#         # graph_enrichment_settings={"use_semantic_clustering": True},
#         run_with_orchestration=False,
#     ).results

#     # After building, list communities
#     resp = client.graphs.list_communities(collection_id=str(collection_id),
#                                           limit=5).results
#     # We cannot guarantee communities are created if no entities or special conditions apply.
#     # If no communities, we may skip this assert or ensure at least no error occurred.
#     assert isinstance(resp, list), "No communities array returned."


def test_list_communities(client: R2RClient, test_collection):
    collection_id = test_collection
    resp = client.graphs.list_communities(collection_id=collection_id,
                                          limit=5).results
    assert isinstance(resp, list), "No results array in communities response"


def test_create_and_get_community(client: R2RClient, test_collection):
    collection_id = test_collection
    community_name = "Test Community"
    community_summary = "Test community summary"

    create_resp = client.graphs.create_community(
        collection_id=collection_id,
        name=community_name,
        summary=community_summary,
        findings=["Finding 1", "Finding 2"],
        rating=8,
    ).results
    community_id = str(create_resp.id)

    resp = client.graphs.get_community(collection_id=collection_id,
                                       community_id=community_id).results
    assert resp.name == community_name, "Community name mismatch"


def test_update_community(client: R2RClient, test_collection):
    collection_id = test_collection
    # Create a community to update
    create_resp = client.graphs.create_community(
        collection_id=collection_id,
        name="Community to update",
        summary="Original summary",
        findings=["Original finding"],
        rating=7,
    ).results
    community_id = str(create_resp.id)

    # Update the community
    resp = client.graphs.update_community(
        collection_id=collection_id,
        community_id=community_id,
        name="Updated Community",
        summary="Updated summary",
        findings=["New finding"],
        rating=9,
    ).results

    assert resp.name == "Updated Community", "Community update failed"


def test_pull_operation(client: R2RClient, test_collection):
    collection_id = test_collection
    resp = client.graphs.pull(collection_id=collection_id).results
    assert resp.success is not None, "No success indicator in pull response"


def test_error_handling(client: R2RClient):
    # Test retrieving a graph with invalid ID
    invalid_id = "not-a-uuid"
    with pytest.raises(R2RException) as exc_info:
        client.graphs.retrieve(collection_id=invalid_id)
    # Expecting a 422 or 404 error. Adjust as per your API's expected response.
    assert exc_info.value.status_code in [
        400,
        422,
        404,
    ], "Expected an error for invalid ID."
