import argparse
import sys
import time
import uuid

from r2r import R2RClient, R2RException


def assert_http_error(condition, message):
    if not condition:
        print("Test failed:", message)
        sys.exit(1)


def create_client(base_url):
    return R2RClient(base_url)


# ---------------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------------


def create_test_conversation():
    """
    Helper function to create a test conversation.
    Returns the created conversation_id.
    """
    resp = client.conversations.create()["results"]
    if not resp.get("id"):
        print("Failed to create test conversation.")
        sys.exit(1)
    return resp["id"]


def delete_test_conversation(conversation_id):
    """
    Helper function to delete a test conversation.
    """
    delete_resp = client.conversations.delete(id=conversation_id)["results"]
    if not delete_resp["success"]:
        print("Failed to delete test conversation:", conversation_id)
        sys.exit(1)


# ---------------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------------


def test_create_conversation():
    print("Testing: Create conversation")
    resp = client.conversations.create()["results"]
    if not resp.get("id"):
        print("Failed to create conversation.")
        sys.exit(1)
    conversation_id = resp["id"]
    print("Conversation created:", conversation_id)
    delete_test_conversation(conversation_id)
    print("Create conversation test passed")
    print("~" * 100)


def test_list_conversations():
    print("Testing: List conversations")
    # Create multiple conversations for pagination test
    conv_ids = [create_test_conversation() for _ in range(3)]
    # List all
    conversations_resp = client.conversations.list()
    conv_list = conversations_resp["results"]
    # Check if at least the 3 we created are present
    created_set = set(conv_ids)
    listed_set = {c["id"] for c in conv_list}
    missing = created_set - listed_set
    if missing:
        print("Some created conversations are not listed:", missing)
        sys.exit(1)
    # Cleanup
    for cid in conv_ids:
        delete_test_conversation(cid)
    print("List conversations test passed")
    print("~" * 100)


def test_retrieve_conversation():
    print("Testing: Retrieve a specific conversation")
    conv_id = create_test_conversation()
    conv_details = client.conversations.retrieve(id=conv_id)["results"]
    # assert_http_error(conv_details["id"] == conv_id, "Retrieved wrong conversation")
    if len(conv_details) != 0:
        print("Retrieved wrong conversation")
        sys.exit(1)
    # Cleanup
    delete_test_conversation(conv_id)
    print("Retrieve conversation test passed")
    print("~" * 100)


def test_delete_conversation():
    print("Testing: Delete a specific conversation")
    conv_id = create_test_conversation()
    delete_resp = client.conversations.delete(id=conv_id)["results"]
    assert_http_error(delete_resp["success"], "Failed to delete conversation")
    # Verify it's gone
    try:
        client.conversations.retrieve(id=conv_id)
        print("Conversation still exists after deletion.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 404, "Unexpected error code after deletion"
        )
    print("Delete conversation test passed")
    print("~" * 100)


def test_add_message():
    print("Testing: Add message to conversation")
    conv_id = create_test_conversation()
    msg_resp = client.conversations.add_message(
        id=conv_id,
        content="Hello",
        role="user",
    )["results"]
    assert_http_error("id" in msg_resp, "Failed to add message")
    retrieved_conv = client.conversations.retrieve(id=conv_id)["results"]
    print(retrieved_conv)
    if len(retrieved_conv) != 1:
        raise Exception("Failed to add message")
    # Cleanup
    delete_test_conversation(conv_id)
    print("Add message test passed")
    print("~" * 100)


def test_list_branches():
    print("Testing: List branches in a conversation")
    conv_id = create_test_conversation()
    # Initially, we should have at least one branch (the default branch)
    branches_resp = client.conversations.list_branches(id=conv_id)
    branches = branches_resp["results"]
    # We expect at least one branch
    assert_http_error(
        len(branches) >= 1, "No branches found in a new conversation"
    )
    # Cleanup
    delete_test_conversation(conv_id)
    print("List branches test passed")
    print("~" * 100)


def test_retrieve_non_existent_conversation():
    print("Testing: Retrieve non-existent conversation")
    bad_id = str(uuid.uuid4())
    try:
        result = client.conversations.retrieve(id=bad_id)
        print(result)
        print("Expected 404 for non-existent conversation, got none.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 404, "Wrong error code for not found"
        )
    print("Retrieve non-existent conversation test passed")
    print("~" * 100)


def test_delete_non_existent_conversation():
    print("Testing: Delete non-existent conversation")
    bad_id = str(uuid.uuid4())
    try:
        client.conversations.delete(id=bad_id)
        print(
            "Expected error deleting non-existent conversation, got success."
        )
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 404, "Wrong error code for delete non-existent"
        )
    print("Delete non-existent conversation test passed")
    print("~" * 100)


def test_add_message_to_non_existent_conversation():
    print("Testing: Add message to non-existent conversation")
    bad_id = str(uuid.uuid4())
    try:
        client.conversations.add_message(
            id=bad_id,
            content="Hi",
            role="user",
        )
        print("Expected error adding message to non-existent conversation.")
        sys.exit(1)
    except R2RException as e:
        # Expected a 404 or a relevant error code
        assert_http_error(
            e.status_code == 404,
            "Wrong error code for message addition in non-existent convo",
        )
    print("Add message to non-existent conversation test passed")
    print("~" * 100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="R2R Conversations SDK Integration Tests"
    )
    parser.add_argument("test_function", help="Test function to run")
    parser.add_argument(
        "--base-url",
        default="http://localhost:7272",
        help="Base URL for the R2R client",
    )
    args = parser.parse_args()

    global client
    client = create_client(args.base_url)

    test_function = args.test_function
    globals()[test_function]()
