import random
import string

from r2r import R2RClient

first_created_chunk_id = "abcc4dd6-5f28-596e-a55b-7cf242ca30aa"
second_created_chunk_id = "abcc4dd6-5f28-596e-a55b-7cf242ca30bb"
created_document_id = "defc4dd6-5f28-596e-a55b-7cf242ca30aa"


# Function to generate a random email
def generate_random_email():
    username_length = 8
    username = "".join(
        random.choices(
            string.ascii_lowercase + string.digits, k=username_length
        )
    )
    domain = random.choice(
        ["example.com", "test.com", "fake.org", "random.net"]
    )
    return f"{username}@{domain}"


user_email = generate_random_email()

client = R2RClient("http://localhost:7276", prefix="/v3")

# First create and authenticate a user if not already done
try:
    new_user = client.users.register(
        email=user_email, password="new_secure_password123"
    )
    print("New user created:", new_user)
except Exception as e:
    print("User might already exist:", str(e))

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

# Test 2: Create chunk and document
print("\n=== Test 2: Create Chunk & Doc. ===")
create_result = client.chunks.create(
    chunks=[
        {
            "id": first_created_chunk_id,
            "document_id": created_document_id,
            "collection_ids": ["b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"],
            "metadata": {"key": "value"},
            "text": "Some text content",
        }
    ],
    run_with_orchestration=False,
)
print("Created chunk:", create_result)

# TODO - Update router and uncomment this test
# TODO - Update router and uncomment this test
# Test 3: Create chunk
# print("\n=== Test 3: Create Chunk & Doc. ===")
# create_result = client.chunks.create(
#     chunks=[
#         {
#             "id": second_created_chunk_id,
#             "document_id": created_document_id,
#             "collection_ids": ["b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"],
#             "metadata": {"key": "value"},
#             "text": "Some text content",
#         }
#     ],
#     run_with_orchestration=False,
# )
# print("Created chunk:", create_result)


# Test 3: Search chunks
print("\n=== Test 3: Search Chunks ===")
search_result = client.chunks.search(query="whoami?")
print("Search results:", search_result)

# Test 4: Retrieve chunk
print("\n=== Test 4: Retrieve Chunk ===")
retrieve_result = client.chunks.retrieve(id=first_created_chunk_id)
print("Retrieved chunk:", retrieve_result)

# Test 5: Update chunk
print("\n=== Test 5: Update Chunk ===")
update_result = client.chunks.update(
    {
        "id": first_created_chunk_id,
        "text": "Updated content",
        "metadata": {"key": "new value"},
    }
)
print("Updated chunk:", update_result)


# Test 4: Retrieve chunk
print("\n=== Test 6: Retrieve Updated Chunk ===")
retrieve_result = client.chunks.retrieve(id=first_created_chunk_id)
print("Retrieved updated chunk:", retrieve_result)
