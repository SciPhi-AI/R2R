from r2r import R2RClient

first_index_name = "index_1"
user_email = "John.Doe1@email.com"

client = R2RClient("http://localhost:7276", prefix="/v3")

# Login
result = client.users.login(
    email=user_email, password="new_secure_password123"
)
print("Login successful")

# Test 1: Create index
print("\n=== Test 1: Create Index ===")
create_result = client.indices.create_index(
    config={
        "index_name": first_index_name,
        "vector_size": 768,
        "index_type": "hnsw",
        "distance_metric": "cosine",
        "max_elements": 1000000,
        "recreate": True,
    },
    run_with_orchestration=False,
)
print("Created index:", create_result)

# Test 2: List indices
print("\n=== Test 2: List Indices ===")
list_result = client.indices.list_indices(limit=10, offset=0)
print("Indices list:", list_result)

# Test 3: Get specific index
print("\n=== Test 3: Get Index ===")
get_result = client.indices.get_index(first_index_name)
print("Index details:", get_result)

# Test 4: Delete index
print("\n=== Test 4: Delete Index ===")
delete_result = client.indices.delete_index(index_name=first_index_name)
print("Deleted index:", delete_result)
