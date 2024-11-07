from r2r import R2RClient

second_ingested_document_id = "b4ac4dd6-5f28-596e-a55b-7cf242ca30aa"
first_chunk_id = "b4ac4dd6-5f28-596e-a55b-7cf242ca30aa"
user_email = "John.Doe1@email.com"

client = R2RClient("http://localhost:7276", prefix="/v3")

# Login
result = client.users.login(
    email=user_email, password="new_secure_password123"
)
print("Login successful")

# Test 1: List chunks
print("\n=== Test 1: List Chunks ===")
list_result = client.chunks.list(
    offset=0,
    limit=10,
    metadata_filter={"key": "value"},
    include_vectors=False,
)
print("Chunks list:", list_result)

# Test 2: Create chunk
print("\n=== Test 2: Create Chunk ===")
create_result = client.chunks.create(
    chunks=[
        {
            "id": first_chunk_id,
            "document_id": second_ingested_document_id,
            "collection_ids": ["b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"],
            "metadata": {"key": "value"},
            "text": "Some text content",
        }
    ],
    run_with_orchestration=False,
)
print("Created chunk:", create_result)

# Test 3: Search chunks
print("\n=== Test 3: Search Chunks ===")
search_result = client.chunks.search(query="whoami?")
print("Search results:", search_result)

# Test 4: Retrieve chunk
print("\n=== Test 4: Retrieve Chunk ===")
retrieve_result = client.chunks.retrieve(id=first_chunk_id)
print("Retrieved chunk:", retrieve_result)

# Test 5: Update chunk
print("\n=== Test 5: Update Chunk ===")
update_result = client.chunks.update(
    {
        "id": first_chunk_id,
        "text": "Updated content",
        "metadata": {"key": "new value"},
    }
)
print("Updated chunk:", update_result)
