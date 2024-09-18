import os

from r2r import R2RClient

if __name__ == "__main__":
    # Initialize the R2R client
    client = R2RClient(
        "http://localhost:7272"
    )  # Replace with your R2R deployment URL

    # Admin login
    print("Logging in as admin...")
    login_result = client.login("admin@example.com", "change_me_immediately")
    print("Admin login result:", login_result)

    # Create two collections
    print("\nCreating two collections...")
    collection1_result = client.create_collection(
        "TestGroup1", "A test collection for document access"
    )
    collection2_result = client.create_collection(
        "TestGroup2", "Another test collection"
    )
    print("Group1 creation result:", collection1_result)
    print("Group2 creation result:", collection2_result)
    collection1_id = collection1_result["results"]["collection_id"]
    collection2_id = collection2_result["results"]["collection_id"]

    # Get collections overview
    print("\nGetting collections overview...")
    collections_overview = client.collections_overview()
    print("Groups overview:", collections_overview)

    # Get specific collection
    print("\nGetting specific collection...")
    collection1_details = client.get_collection(collection1_id)
    print("Group1 details:", collection1_details)

    # List all collections
    print("\nListing all collections...")
    collections_list = client.list_collections()
    print("Groups list:", collections_list)

    # Update a collection
    print("\nUpdating Group1...")
    update_result = client.update_collection(
        collection1_id,
        name="UpdatedTestGroup1",
        description="Updated description",
    )
    print("Group update result:", update_result)

    # Ingest two documents
    print("\nIngesting two documents...")
    script_path = os.path.dirname(__file__)
    sample_file1 = os.path.join(
        script_path, "core", "examples", "data", "aristotle_v2.txt"
    )
    sample_file2 = os.path.join(
        script_path, "core", "examples", "data", "aristotle.txt"
    )
    ingestion_result1 = client.ingest_files([sample_file1])
    ingestion_result2 = client.ingest_files([sample_file2])
    print("Document1 ingestion result:", ingestion_result1)
    print("Document2 ingestion result:", ingestion_result2)
    document1_id = ingestion_result1["results"]["processed_documents"][0]["id"]
    document2_id = ingestion_result2["results"]["processed_documents"][0]["id"]

    # Assign documents to collections
    print("\nAssigning documents to collections...")
    assign_result1 = client.assign_document_to_collection(
        document1_id, collection1_id
    )
    assign_result2 = client.assign_document_to_collection(
        document2_id, collection2_id
    )
    print("Document1 assignment result:", assign_result1)
    print("Document2 assignment result:", assign_result2)

    # document1_id = "c3291abf-8a4e-5d9d-80fd-232ef6fd8526"
    # Get document collections
    print("\nGetting collections for Document1...")
    doc1_collections = client.document_collections(document1_id)
    print("Document1 collections:", doc1_collections)

    # Create three test users
    print("\nCreating three test users...")
    user1_result = client.register("user1@test.com", "password123")
    user2_result = client.register("user2@test.com", "password123")
    user3_result = client.register("user3@test.com", "password123")
    print("User1 creation result:", user1_result)
    print("User2 creation result:", user2_result)
    print("User3 creation result:", user3_result)

    # Add users to collections
    print("\nAdding users to collections...")
    add_user1_result = client.add_user_to_collection(
        user1_result["results"]["id"], collection1_id
    )
    add_user2_result = client.add_user_to_collection(
        user2_result["results"]["id"], collection2_id
    )
    add_user3_result1 = client.add_user_to_collection(
        user3_result["results"]["id"], collection1_id
    )
    add_user3_result2 = client.add_user_to_collection(
        user3_result["results"]["id"], collection2_id
    )
    print("Add user1 to collection1 result:", add_user1_result)
    print("Add user2 to collection2 result:", add_user2_result)
    print("Add user3 to collection1 result:", add_user3_result1)
    print("Add user3 to collection2 result:", add_user3_result2)

    # Get users in a collection
    print("\nGetting users in Group1...")
    users_in_collection1 = client.user_collections(collection1_id)
    print("Users in Group1:", users_in_collection1)

    # Get collections for a user
    print("\nGetting collections for User3...")
    user3_collections = client.user_collections(user3_result["results"]["id"])
    print("User3 collections:", user3_collections)

    # Get documents in a collection
    print("\nGetting documents in Group1...")
    docs_in_collection1 = client.documents_in_collection(collection1_id)
    print("Documents in Group1:", docs_in_collection1)

    # Remove user from collection
    print("\nRemoving User3 from Group1...")
    remove_user_result = client.remove_user_from_collection(
        user3_result["results"]["id"], collection1_id
    )
    print("Remove user result:", remove_user_result)

    # Remove document from collection
    print("\nRemoving Document1 from Group1...")
    remove_doc_result = client.remove_document_from_collection(
        document1_id, collection1_id
    )
    print("Remove document result:", remove_doc_result)

    # Logout admin
    print("\nLogging out admin...")
    client.logout()

    # Login as user1
    print("\nLogging in as user1...")
    client.login("user1@test.com", "password123")

    # Search for documents (should see document1 but not document2)
    print("\nUser1 searching for documents...")
    search_result_user1 = client.search(
        "philosophy", {"selected_collection_ids": [collection1_id]}
    )
    print("User1 search result:", search_result_user1)

    # Logout user1
    print("\nLogging out user1...")
    client.logout()

    # Login as user3
    print("\nLogging in as user3...")
    client.login("user3@test.com", "password123")

    # Search for documents (should see only document2 after removal from Group1)
    print("\nUser3 searching for documents...")
    try:
        search_result_user3 = client.search(
            "philosophy",
            {"selected_collection_ids": [collection1_id, collection2_id]},
        )
    except Exception as e:
        print("User3 search result error:", e)
        search_result_user3 = client.search(
            "philosophy", {"selected_collection_ids": [collection2_id]}
        )

    print("User3 search result:", search_result_user3)

    # Logout user3
    print("\nLogging out user3...")
    client.logout()

    # Clean up
    print("\nCleaning up...")
    # Login as admin again
    client.login("admin@example.com", "change_me_immediately")

    # Delete the collections
    print("Deleting the collections...")
    client.delete_collection(collection1_id)
    client.delete_collection(collection2_id)

    # Logout admin
    print("\nLogging out admin...")
    client.logout()

    print("\nWorkflow completed.")
