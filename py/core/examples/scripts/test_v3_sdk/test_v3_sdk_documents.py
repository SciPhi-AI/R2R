from r2r import R2RClient

first_ingested_document_id = "1b594aea-583a-5a4b-92f4-229d6e5eb886"
first_ingested_file_path = "../../data/pg_essay_1.html"
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

# Test 1: List documents
print("\n=== Test 1: List Documents ===")
list_result = client.documents.list(limit=10, offset=0)
print("Documents list:", list_result)

# Test 2: Create document
print("\n=== Test 2: Create Document ===")
create_result = client.documents.create(
    file_path=first_ingested_file_path,
    metadata={"metadata_1": "some random metadata"},
    run_with_orchestration=False,
    id=None,
)
print("Created document:", create_result)

# Test 3: Retrieve document
print("\n=== Test 3: Retrieve Document ===")
retrieve_result = client.documents.retrieve(id=first_ingested_document_id)
print("Retrieved document:", retrieve_result)

# Test 4: Update document
print("\n=== Test 4: Update Document ===")
update_result = client.documents.update(
    file_path=first_ingested_file_path, id=first_ingested_document_id
)
print("Updated document:", update_result)

# Test 5: List document chunks
print("\n=== Test 5: List Document Chunks ===")
chunks_result = client.documents.list_chunks(id=first_ingested_document_id)
print("Document chunks:", chunks_result)

# Test 6: List document collections
client.users.logout()
print("\n=== Test 6: List Document Collections ===")
collections_result = client.documents.list_collections(
    id=first_ingested_document_id, offset=0, limit=10
)
print("Document collections:", collections_result)

# Test 7: Delete document (commented out for safety)
# print("\n=== Test 7: Delete Document ===")
# delete_result = client.documents.delete(id=first_ingested_document_id)
# print("Deleted document:", delete_result)
