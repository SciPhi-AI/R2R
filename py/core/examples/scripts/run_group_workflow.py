import os

from r2r import R2RClient

if __name__ == "__main__":
    # Initialize the R2R client
    client = R2RClient(
        "http://localhost:8000"
    )  # Replace with your R2R deployment URL

    # Admin login
    print("Logging in as admin...")
    login_result = client.login("admin@example.com", "change_me_immediately")
    print("Admin login result:", login_result)

    # Create two groups
    print("\nCreating two groups...")
    group1_result = client.create_group(
        "TestGroup1", "A test group for document access"
    )
    group2_result = client.create_group("TestGroup2", "Another test group")
    print("Group1 creation result:", group1_result)
    print("Group2 creation result:", group2_result)
    group1_id = group1_result["results"]["group_id"]
    group2_id = group2_result["results"]["group_id"]

    # Get groups overview
    print("\nGetting groups overview...")
    groups_overview = client.groups_overview()
    print("Groups overview:", groups_overview)

    # Get specific group
    print("\nGetting specific group...")
    group1_details = client.get_group(group1_id)
    print("Group1 details:", group1_details)

    # List all groups
    print("\nListing all groups...")
    groups_list = client.list_groups()
    print("Groups list:", groups_list)

    # Update a group
    print("\nUpdating Group1...")
    update_result = client.update_group(
        group1_id, name="UpdatedTestGroup1", description="Updated description"
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

    # Assign documents to groups
    print("\nAssigning documents to groups...")
    assign_result1 = client.assign_document_to_group(document1_id, group1_id)
    assign_result2 = client.assign_document_to_group(document2_id, group2_id)
    print("Document1 assignment result:", assign_result1)
    print("Document2 assignment result:", assign_result2)

    # document1_id = "c3291abf-8a4e-5d9d-80fd-232ef6fd8526"
    # Get document groups
    print("\nGetting groups for Document1...")
    doc1_groups = client.document_groups(document1_id)
    print("Document1 groups:", doc1_groups)

    # Create three test users
    print("\nCreating three test users...")
    user1_result = client.register("user1@test.com", "password123")
    user2_result = client.register("user2@test.com", "password123")
    user3_result = client.register("user3@test.com", "password123")
    print("User1 creation result:", user1_result)
    print("User2 creation result:", user2_result)
    print("User3 creation result:", user3_result)

    # Add users to groups
    print("\nAdding users to groups...")
    add_user1_result = client.add_user_to_group(
        user1_result["results"]["id"], group1_id
    )
    add_user2_result = client.add_user_to_group(
        user2_result["results"]["id"], group2_id
    )
    add_user3_result1 = client.add_user_to_group(
        user3_result["results"]["id"], group1_id
    )
    add_user3_result2 = client.add_user_to_group(
        user3_result["results"]["id"], group2_id
    )
    print("Add user1 to group1 result:", add_user1_result)
    print("Add user2 to group2 result:", add_user2_result)
    print("Add user3 to group1 result:", add_user3_result1)
    print("Add user3 to group2 result:", add_user3_result2)

    # Get users in a group
    print("\nGetting users in Group1...")
    users_in_group1 = client.user_groups(group1_id)
    print("Users in Group1:", users_in_group1)

    # Get groups for a user
    print("\nGetting groups for User3...")
    user3_groups = client.user_groups(user3_result["results"]["id"])
    print("User3 groups:", user3_groups)

    # Get documents in a group
    print("\nGetting documents in Group1...")
    docs_in_group1 = client.documents_in_group(group1_id)
    print("Documents in Group1:", docs_in_group1)

    # Remove user from group
    print("\nRemoving User3 from Group1...")
    remove_user_result = client.remove_user_from_group(
        user3_result["results"]["id"], group1_id
    )
    print("Remove user result:", remove_user_result)

    # Remove document from group
    print("\nRemoving Document1 from Group1...")
    remove_doc_result = client.remove_document_from_group(
        document1_id, group1_id
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
        "philosophy", {"selected_group_ids": [group1_id]}
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
            "philosophy", {"selected_group_ids": [group1_id, group2_id]}
        )
    except Exception as e:
        print("User3 search result error:", e)
        search_result_user3 = client.search(
            "philosophy", {"selected_group_ids": [group2_id]}
        )

    print("User3 search result:", search_result_user3)

    # Logout user3
    print("\nLogging out user3...")
    client.logout()

    # Clean up
    print("\nCleaning up...")
    # Login as admin again
    client.login("admin@example.com", "change_me_immediately")

    # Delete the groups
    print("Deleting the groups...")
    client.delete_group(group1_id)
    client.delete_group(group2_id)

    # Logout admin
    print("\nLogging out admin...")
    client.logout()

    print("\nWorkflow completed.")
