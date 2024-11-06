import asyncio

from r2r import R2RClient

user_email = "John.Doe1@email.com"
client = R2RClient("http://localhost:7276", prefix="/v3")

# # First create and authenticate a user if not already done
# try:
#     new_user = client.users.register(
#         email=user_email, password="new_secure_password123"
#     )
#     print("New user created:", new_user)
# except Exception as e:
#     print("User might already exist:", str(e))

# # Login to get necessary tokens
# result = client.users.login(
#     email=user_email, password="new_secure_password123"
# )
# print("Login successful")

# Test 1: Create a new prompt
print("\n=== Test 1: Create Prompt ===")
create_result = client.prompts.create(
    name="greeting_prompt",
    template="Hello, {name}!",
    input_types={"name": "string"},
)
print("Created prompt:", create_result)

# Test 2: List prompts
print("\n=== Test 2: List Prompts ===")
list_result = client.prompts.list()
print("Prompts list:", list_result)

# Test 3: Get specific prompt
print("\n=== Test 3: Get Prompt Details ===")
get_result = client.prompts.retrieve(
    name="greeting_prompt",
    inputs={"name": "John"},
    prompt_override="Hi, {name}!",
)
print("Prompt details:", get_result)

# Test 4: Update prompt
print("\n=== Test 4: Update Prompt ===")
update_result = client.prompts.update(
    name="greeting_prompt",
    template="Greetings, {name}!",
    input_types={"name": "string", "age": "integer"},
)
print("Updated prompt:", update_result)

# Test 5: Retrieve updated prompt
print("\n=== Test 5: Retrieve Updated Prompt ===")
get_updated_result = client.prompts.retrieve(
    name="greeting_prompt", inputs={"name": "John", "age": 30}
)
print("Updated prompt details:", get_updated_result)

# Test 6: Delete prompt
print("\n=== Test 6: Delete Prompt ===")
delete_result = client.prompts.delete(name="greeting_prompt")
print("Deleted prompt:", delete_result)

# Test 7: Verify deletion by trying to get the prompt (should fail)
print("\n=== Test 7: Verify Deletion ===")
try:
    client.prompts.retrieve(name="greeting_prompt")
    print("ERROR: Prompt still exists!")
except Exception as e:
    print("Successfully verified prompt deletion:", str(e))
