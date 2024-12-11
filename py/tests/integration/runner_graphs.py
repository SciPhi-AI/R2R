import argparse
import sys
import uuid

from r2r import R2RClient, R2RException


def assert_http_error(condition, message):
    if not condition:
        print("Test failed:", message)
        sys.exit(1)


def test_list_graphs():
    print("Testing: List graphs")
    resp = client.graphs.list(limit=5)
    assert_http_error("results" in resp, "No results field in list response")
    print("List graphs test passed")
    print("~" * 100)


def test_create_and_get_graph():
    print("Testing: Create and get graph")
    # First create a collection since graphs are tied to collections
    resp = client.collections.create(
        name="Test Collection", description="A sample collection for testing"
    )["results"]
    collection_id = resp["id"]

    # Get the graph details
    resp = client.graphs.retrieve(collection_id=collection_id)["results"]
    assert_http_error(
        resp["collection_id"] == collection_id, "Graph ID mismatch"
    )
    print("Create and get graph test passed")
    print("~" * 100)


def test_update_graph():
    print("Testing: Update graph")
    collections = client.collections.list(limit=1)["results"]
    collection_id = collections[0]["id"]
    new_name = "Updated Test Graph"
    new_description = "Updated test description"

    resp = client.graphs.update(
        collection_id=collection_id, name=new_name, description=new_description
    )["results"]

    assert_http_error(resp["name"] == new_name, "Name not updated correctly")
    assert_http_error(
        resp["description"] == new_description,
        "Description not updated correctly",
    )
    print("Update graph test passed")
    print("~" * 100)


def test_list_entities():
    print("Testing: List entities")
    collections = client.collections.list(limit=1)["results"]
    collection_id = collections[0]["id"]
    resp = client.graphs.list_entities(collection_id=collection_id, limit=5)[
        "results"
    ]
    assert_http_error(
        isinstance(resp, list), "No results array in entities response"
    )
    print("List entities test passed")
    print("~" * 100)


def test_create_and_get_entity():
    print("Testing: Create and get entity")
    collections = client.collections.list(limit=1)["results"]
    collection_id = collections[0]["id"]
    entity_name = "Test Entity"
    entity_description = "Test entity description"

    # Create entity first using the create_entity endpoint
    create_resp = client.graphs.create_entity(
        collection_id=collection_id,
        name=entity_name,
        description=entity_description,
    )["results"]
    entity_id = create_resp["id"]

    # Then retrieve it
    resp = client.graphs.get_entity(
        collection_id=collection_id, entity_id=entity_id
    )["results"]

    assert_http_error(resp["name"] == entity_name, "Entity name mismatch")
    print("Create and get entity test passed")
    print("~" * 100)


def test_list_relationships():
    print("Testing: List relationships")
    collections = client.collections.list(limit=1)["results"]
    collection_id = collections[0]["id"]
    resp = client.graphs.list_relationships(
        collection_id=collection_id, limit=5
    )["results"]
    assert_http_error(
        isinstance(resp, list), "No results array in relationships response"
    )
    print("List relationships test passed")
    print("~" * 100)


def test_create_and_get_relationship():
    print("Testing: Create and get relationship")
    collections = client.collections.list(limit=1)["results"]
    collection_id = collections[0]["id"]

    # Create two entities first
    entity1 = client.graphs.create_entity(
        collection_id=collection_id,
        name="Entity 1",
        description="Entity 1 description",
    )["results"]
    entity2 = client.graphs.create_entity(
        collection_id=collection_id,
        name="Entity 2",
        description="Entity 2 description",
    )["results"]

    # Create relationship
    rel_resp = client.graphs.create_relationship(
        collection_id=collection_id,
        subject="Entity 1",
        subject_id=entity1["id"],
        predicate="related_to",
        object="Entity 2",
        object_id=entity2["id"],
        description="Test relationship",
    )["results"]
    relationship_id = rel_resp["id"]

    # Get relationship
    resp = client.graphs.get_relationship(
        collection_id=collection_id, relationship_id=relationship_id
    )["results"]

    assert_http_error(
        resp["predicate"] == "related_to", "Relationship predicate mismatch"
    )
    print("Create and get relationship test passed")
    print("~" * 100)


def test_build_communities():
    print("Testing: Build communities")
    collections = client.collections.list(limit=1)["results"]
    collection_id = collections[0]["id"]
    resp = client.graphs.build(
        collection_id=collection_id,
        run_type="run",
        settings={"use_semantic_clustering": True},
    )["results"]
    # assert_http_error("task_id" in resp or "success" in resp, "No task_id or success indicator in response")
    resp = client.graphs.list_communities(
        collection_id=collection_id, limit=5
    )["results"]
    if len(resp) == 0:
        print("No communities found")
        raise Exception("No communities found")
    print("Build communities test passed")
    print("~" * 100)


def test_list_communities():
    print("Testing: List communities")
    collections = client.collections.list(limit=1)["results"]
    collection_id = collections[0]["id"]
    resp = client.graphs.list_communities(
        collection_id=collection_id, limit=5
    )["results"]
    assert_http_error(
        isinstance(resp, list), "No results array in communities response"
    )
    print("List communities test passed")
    print("~" * 100)


def test_create_and_get_community():
    print("Testing: Create and get community")
    collections = client.collections.list(limit=1)["results"]
    collection_id = collections[0]["id"]
    community_name = "Test Community"
    community_summary = "Test community summary"

    # Create community
    create_resp = client.graphs.create_community(
        collection_id=collection_id,
        name=community_name,
        summary=community_summary,
        findings=["Finding 1", "Finding 2"],
        rating=8,
    )["results"]
    community_id = create_resp["id"]

    # Get community
    resp = client.graphs.get_community(
        collection_id=collection_id, community_id=community_id
    )["results"]

    assert_http_error(
        resp["name"] == community_name, "Community name mismatch"
    )
    print("Create and get community test passed")
    print("~" * 100)


def test_update_community():
    print("Testing: Update community")
    collections = client.collections.list(limit=1)["results"]
    collection_id = collections[0]["id"]

    # First create a community to update
    create_resp = client.graphs.create_community(
        collection_id=collection_id,
        name="Test Community",
        summary="Original summary",
        findings=["Original finding"],
        rating=7,
    )["results"]
    community_id = create_resp["id"]

    # Update the community
    resp = client.graphs.update_community(
        collection_id=collection_id,
        community_id=community_id,
        name="Updated Community",
        summary="Updated summary",
        findings=["New finding"],
        rating=9,
    )["results"]

    assert_http_error(
        resp["name"] == "Updated Community", "Community update failed"
    )
    print("Update community test passed")
    print("~" * 100)


def test_pull_operation():
    print("Testing: Pull operation")
    collections = client.collections.list(limit=1)["results"]
    collection_id = collections[0]["id"]
    resp = client.graphs.pull(collection_id=collection_id)["results"]
    assert_http_error(
        "success" in resp, "No success indicator in pull response"
    )
    print("Pull operation test passed")
    print("~" * 100)


def test_error_handling():
    print("Testing: Error handling")
    try:
        client.graphs.retrieve(collection_id="invalid-id")
        print("Expected error for invalid ID, got none.")
        sys.exit(1)
    except R2RException as e:
        print("Caught expected error for invalid ID:", str(e))
    print("Error handling test passed")
    print("~" * 100)


def create_client(base_url):
    return R2RClient(base_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="R2R SDK Graph Integration Tests"
    )
    parser.add_argument("test_function", help="Test function to run")
    parser.add_argument(
        "--base-url",
        default="http://localhost:7272",
        help="Base URL for the R2R client",
    )
    args = parser.parse_args()

    global client
    client = create_client(args.base_url)

    test_function = args.test_function
    globals()[test_function]()
