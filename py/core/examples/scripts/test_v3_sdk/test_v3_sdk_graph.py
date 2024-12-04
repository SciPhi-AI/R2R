import time
import uuid

from r2r import R2RClient

# Initialize client
client = R2RClient("http://localhost:7276", prefix="/v3")


def setup_prerequisites():
    """Setup necessary document and collection"""
    print("\n=== Setting up prerequisites ===")

    # # Login
    # try:
    #     client.users.register(email=user_email, password="new_secure_password123")
    # except Exception as e:
    #     print("User might already exist:", str(e))

    # result = client.users.login(email=user_email, password="new_secure_password123")
    # print("Login successful")

    try:
        # Create document
        doc_result = client.documents.create(
            file_path="../../data/pg_essay_1.html",
            metadata={"source": "test"},
            run_with_orchestration=False,
        )
        print("doc_id = ", doc_result)
        doc_id = doc_result["results"]["document_id"]
        print(f"Created document with ID: {doc_id}")
    except Exception as e:
        doc_id = "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
        pass

    # Create collection
    # collection_id = str(uuid.uuid4())
    collection_result = client.collections.create(
        # collection_id=collection_id,
        name="Test Collection",
        description="Collection for testing graph operations",
    )
    print(
        "Created collection with ID: "
        + str(collection_result["results"]["collection_id"])
    )
    collection_id = collection_result["results"]["collection_id"]
    # Add document to collection
    client.collections.add_document(id=collection_id, document_id=doc_id)
    print(f"Added document {doc_id} to collection {collection_id}")

    return collection_id, doc_id


def test_graph_operations(collection_id):
    """Test graph CRUD operations"""
    print("\n=== Testing Graph Operations ===")

    # Test 1: Create Graph
    print("\n--- Test 1: Create Graph ---")
    create_result = client.graphs.create(
        collection_id=collection_id,
        settings={
            "entity_types": ["PERSON", "ORG", "GPE"],
            "min_confidence": 0.8,
        },
        run_type="estimate",
        run_with_orchestration=False,
    )
    print("Graph estimation result:", create_result)

    create_result = client.graphs.create(
        collection_id=collection_id,
        settings={
            "entity_types": ["PERSON", "ORG", "GPE"],
            "min_confidence": 0.8,
        },
        run_type="run",
        run_with_orchestration=False,
    )
    print("Graph creation result:", create_result)

    # # # Test 2: Get Graph Status
    # # print("\n--- Test 2: Get Graph Status ---")
    # # status_result = client.graphs.get_status(collection_id=collection_id)
    # # print("Graph status:", status_result)

    # Test 3: List Entities
    print("\n--- Test 3: List Entities ---")
    entities_result = client.graphs.list_entities(
        collection_id=collection_id,
        # level="collection",
        offset=0,
        limit=10,
    )
    print("Entities:", entities_result)

    # Test 4: Get Specific Entity
    print(
        'entities_result["results"]["entities"][0] = ',
        entities_result["results"]["entities"][0],
    )
    entity_id = entities_result["results"]["entities"][0][
        "id"
    ]  # entities_result['items'][0]['id']
    print("entity_id = ", entity_id)
    print(f"\n--- Test 4: Get Entity {entity_id} ---")
    entity_result = client.graphs.get_entity(
        collection_id=collection_id, entity_id=entity_id
    )
    print("Entity details:", entity_result)

    # # # # Test 5: List Relationships
    # # # print("\n--- Test 5: List Relationships ---")
    # # relationships_result = client.graphs.list_relationships(
    # #     collection_id=collection_id,
    # #     offset=0,
    # #     limit=10
    # # )
    # # print("Relationships:", relationships_result)

    # Test 6: Create Communities
    print("\n--- Test 6: Create Communities ---")
    communities_result = client.graphs.create_communities(
        run_type="estimate",
        collection_id=collection_id,
        run_with_orchestration=False,
        # settings={
        #     "algorithm": "louvain",
        #     "resolution": 1.0,
        #     "min_community_size": 3
        # }
    )
    print("Communities estimation result:", communities_result)

    communities_result = client.graphs.create_communities(
        run_type="run",
        collection_id=collection_id,
        run_with_orchestration=False,
        # settings={
        #     "algorithm": "louvain",
        #     "resolution": 1.0,
        #     "min_community_size": 3
        # }
    )
    print("Communities creation result:", communities_result)

    # Wait for community creation to complete

    # Test 7: List Communities
    print("\n--- Test 7: List Communities ---")
    communities_list = client.graphs.list_communities(
        collection_id=collection_id, offset=0, limit=10
    )
    print("Communities:", communities_list)

    # Test 8: Tune Prompt
    print("\n--- Test 8: Tune Prompt ---")
    tune_result = client.graphs.tune_prompt(
        collection_id=collection_id,
        prompt_name="graphrag_relationships_extraction_few_shot",
        documents_limit=100,
        chunks_limit=1000,
    )
    print("Prompt tuning result:", tune_result)

    # Test 9: Entity Deduplication
    print("\n--- Test 9: Entity Deduplication ---")
    dedup_result = client.graphs.deduplicate_entities(
        collection_id=collection_id,
        settings={
            "graph_entity_deduplication_type": "by_name",
            "max_description_input_length": 65536,
        },
    )
    print("Deduplication result:", dedup_result)

    # Optional: Clean up
    # Test 10: Delete Graph
    print("\n--- Test 10: Delete Graph ---")
    delete_result = client.graphs.delete(
        collection_id=collection_id, cascade=True
    )
    print("Graph deletion result:", delete_result)


def main():
    try:
        # Setup prerequisites
        # collection_id, doc_id = setup_prerequisites()
        collection_id = "42e0efa8-ab92-49e8-ae5b-84215876a632"

        # Run graph operations tests
        test_graph_operations(collection_id)

    except Exception as e:
        print(f"Error occurred: {str(e)}")
    finally:
        pass
        # Cleanup: Logout
        # client.users.logout()
        # print("\nLogged out successfully")


if __name__ == "__main__":
    main()
