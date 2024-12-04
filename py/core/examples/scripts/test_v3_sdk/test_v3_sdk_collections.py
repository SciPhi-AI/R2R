from r2r import R2RClient

user_email = "John.Doe1@email.com"

client = R2RClient("http://localhost:7276", prefix="/v3")

# First create and authenticate a user if not already done
try:
    new_user = client.users.register(
        email=user_email, password="new_secure_password123"
    )
    print("New user created:", new_user)
except Exception as e:
    print("User might already exist:", str(e))

# Login to get necessary tokens
result = client.users.login(
    email=user_email, password="new_secure_password123"
)
print("Login successful")

# # Test 1: Create a new collection
print("\n=== Test 1: Create Collection ===")
create_result = client.collections.create(
    name="Test Collection",
    description="A test collection for integration testing",
)
print("Created collection:", create_result)
collection_id = create_result["results"]["collection_id"]

# Test 2: List collections
# print("\n=== Test 2: List Collections ===")
list_result = client.collections.list(offset=0, limit=10)
print("Collections list:", list_result)

# Test 3: Get specific collection
print("\n=== Test 3: Get Collection Details ===")
get_result = client.collections.retrieve(
    id="3642055e-07aa-5741-986e-6d1b47a8a79c"
)
print("Collection details:", get_result)

# Test 4: Update collection
print("\n=== Test 4: Update Collection ===")
update_result = client.collections.update(
    id=collection_id,
    name="Updated Test Collection",
    description="Updated description for testing",
)
print("Updated collection:", update_result)

# # Test 5: Add document to collection
# list user documents
documents = client.documents.list(limit=10, offset=0)
print(documents)

print("\n=== Test 5: Add Document to Collection ===")
add_doc_result = client.collections.add_document(
    id=collection_id, document_id=documents["results"][0]["id"]
)
print("Added document to collection:", add_doc_result)

# Test 6: List documents in collection
print("\n=== Test 6: List Collection Documents ===")
docs_result = client.collections.list_documents(
    id=collection_id, offset=0, limit=10
)
print("Collection documents:", docs_result)

# Test 7: Get collection users
print("\n=== Test 7: List Collection Users ===")
users_result = client.collections.list_users(
    id=collection_id, offset=0, limit=10
)
print("Collection users:", users_result)

# Test 8: Remove document from collection
print("\n=== Test 8: Remove Document from Collection ===")
remove_doc_result = client.collections.remove_document(
    id=collection_id, document_id=documents["results"][0]["id"]
)
print("Removed document from collection:", remove_doc_result)

# Test 9: Delete collection
print("\n=== Test 9: Delete Collection ===")
delete_result = client.collections.delete(id=collection_id)
print("Deleted collection:", delete_result)

# # Verify deletion by trying to get the collection (should fail)
# print("\n=== Test 10: Verify Deletion ===")
# try:
#     client.collections.retrieve(id=collection_id)
#     print("ERROR: Collection still exists!")
# except Exception as e:
#     print("Successfully verified collection deletion:", str(e))
