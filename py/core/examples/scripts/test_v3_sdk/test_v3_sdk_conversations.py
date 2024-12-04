import asyncio
import json

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

# Test 1: Create a new conversation
print("\n=== Test 1: Create Conversation ===")
create_result = client.conversations.create()
print("Created conversation:", create_result)
conversation_id = create_result["results"]["conversation_id"]

# Test 2: List conversations
print("\n=== Test 2: List Conversations ===")
list_result = client.conversations.list(offset=0, limit=10)
print("Conversations list:", list_result)

# Test 3: Get specific conversation
print("\n=== Test 3: Get Conversation Details ===")
get_result = client.conversations.retrieve(id=conversation_id)
print("Conversation details:", get_result)

# Test 4: Add message to conversation
print("\n=== Test 4: Add Message to Conversation ===")
add_message_result = client.conversations.add_message(
    id=conversation_id,
    content="Hello, this is a test message!",
    role="user",
    metadata={"test_key": "test_value"},
)
print("Added message to conversation:", add_message_result)
message_id = add_message_result["results"]["message_id"]

# # Test 5: Update message in conversation
print("\n=== Test 5: Update Message in Conversation ===")
update_message_result = client.conversations.update_message(
    id=conversation_id,
    message_id=message_id,
    content="Updated test message content",
)
print("Updated message in conversation:", update_message_result)

# # Test 6: List branches in conversation
print("\n=== Test 6: List Branches in Conversation ===")
branches_result = client.conversations.list_branches(id=conversation_id)
print("Conversation branches:", branches_result)

# Verify deletion by trying to get the conversation (should fail)
print("\n=== Test 7: Retrieve Conversation ===")
result = client.conversations.retrieve(id=conversation_id)
print("Retrieved conversation:", result)


# # Test 7: Delete conversation
print("\n=== Test 7.5: Delete Conversation ===")
delete_result = client.conversations.delete(id=conversation_id)
print("Deleted conversation:", delete_result)

# Verify deletion by trying to get the conversation (should fail)
print("\n=== Test 8: Verify Deletion ===")
try:
    result = client.conversations.retrieve(id=conversation_id)
    if result["results"] != []:
        print("ERROR: Conversation still exists!")
except Exception as e:
    print("Successfully verified conversation deletion:", str(e))

# Run the async test function
# async def test_conversations():
# asyncio.run(test_conversations())
