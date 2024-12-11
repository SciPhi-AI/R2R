import argparse
import sys
import time
import uuid
from dataclasses import dataclass
from typing import List, Optional

from r2r import R2RClient, R2RException


@dataclass
class TestUser:
    email: str
    password: str
    client: R2RClient
    user_id: Optional[str] = None


def assert_http_error(condition, message):
    if not condition:
        print("Test failed:", message)
        sys.exit(1)


def create_test_user(base_url: str) -> TestUser:
    """Create a new test user with random credentials"""
    random_string = str(uuid.uuid4())
    email = f"test_{random_string}@example.com"
    password = f"pass_{random_string}"

    client = R2RClient(base_url)
    user = client.users.register(email, password)["results"]
    client.users.login(email, password)

    return TestUser(
        email=email, password=password, client=client, user_id=user["id"]
    )


def create_test_document(
    client: R2RClient, content: str, collection_ids: List[str] = None
) -> str:
    """Create a test document and return its ID"""
    response = client.documents.create(
        raw_text=content,
        collection_ids=collection_ids,
        run_with_orchestration=False,
    )["results"]
    return response["document_id"]


def create_test_collection(client: R2RClient, name: str) -> str:
    """Create a test collection and return its ID"""
    # Assuming there's a collections API endpoint
    response = client.collections.create(name=name)["results"]
    return response["id"]


def test_document_sharing_via_collections():
    print("Testing: Document sharing between users via collections")

    # Create two test users
    user1 = create_test_user(args.base_url)
    user2 = create_test_user(args.base_url)

    # User1 creates a collection
    print("creating collection")
    collection_id = create_test_collection(user1.client, "Shared Collection")

    # User1 creates a document in the collection
    doc_content = f"Shared document content {uuid.uuid4()}"
    print("creating document")

    doc_id = create_test_document(user1.client, doc_content, [collection_id])

    print("Adding document")
    # Add user2 to the collection
    user1.client.users.add_to_collection(user2.user_id, collection_id)

    # # Verify user2 can access the document
    # try:
    #     doc = user2.client.documents.retrieve(id=doc_id)["results"]
    #     assert_http_error(doc["id"] == doc_id, "User2 couldn't access shared document")
    # except R2RException as e:
    #     print(f"User2 failed to access shared document: {e}")
    #     sys.exit(1)

    # print("Document sharing via collections test passed")
    # print("~" * 100)


def test_document_access_restrictions():
    print("Testing: Document access restrictions between users")

    # Create two test users
    user1 = create_test_user(args.base_url)
    user2 = create_test_user(args.base_url)

    # User1 creates a private document
    doc_content = f"Private document content {uuid.uuid4()}"
    doc_id = create_test_document(user1.client, doc_content)

    # Verify user2 cannot access the document
    try:
        user2.client.documents.retrieve(id=doc_id)
        print("Expected 403 for accessing private document")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 403,
            "Wrong error code for unauthorized document access",
        )

    print("Document access restrictions test passed")
    print("~" * 100)


def test_collection_document_removal():
    print("Testing: Document access after collection removal")

    # Create test users
    user1 = create_test_user(args.base_url)
    user2 = create_test_user(args.base_url)

    # User1 creates a collection
    collection_id = create_test_collection(
        user1.client, "Temporary Collection"
    )

    # User1 creates a document in the collection
    doc_content = f"Collection document content {uuid.uuid4()}"
    doc_id = create_test_document(user1.client, doc_content, [collection_id])

    # Add user2 to collection
    user1.client.users.add_to_collection(user2.user_id, collection_id)

    # Verify initial access
    doc = user2.client.documents.retrieve(id=doc_id)["results"]
    assert_http_error(doc["id"] == doc_id, "Initial access failed")

    # Remove user2 from collection
    user1.client.users.remove_from_collection(user2.user_id, collection_id)

    # Verify user2 can no longer access the document
    try:
        user2.client.documents.retrieve(id=doc_id)
        print("Expected 403 after collection removal")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 403, "Wrong error code after collection removal"
        )

    print("Collection document removal test passed")
    print("~" * 100)


def test_document_search_across_users():
    print("Testing: Document search visibility across users")

    # Create test users
    user1 = create_test_user(args.base_url)
    user2 = create_test_user(args.base_url)

    # Create unique search term
    search_term = f"unique_term_{uuid.uuid4()}"

    # User1 creates documents
    doc1_content = f"Private document with {search_term}"
    private_doc_id = create_test_document(user1.client, doc1_content)

    # Create shared collection
    collection_id = create_test_collection(
        user1.client, "Search Test Collection"
    )
    doc2_content = f"Shared document with {search_term}"
    shared_doc_id = create_test_document(
        user1.client, doc2_content, [collection_id]
    )

    # Add user2 to collection
    user1.client.users.add_to_collection(user2.user_id, collection_id)

    # Wait for search indexing
    time.sleep(1)

    # User2 searches for documents
    search_results = user2.client.documents.search(
        query=search_term, search_mode="custom", search_settings={"limit": 10}
    )["results"]

    # Verify user2 only sees shared document
    visible_doc_ids = [doc["id"] for doc in search_results]
    assert_http_error(
        shared_doc_id in visible_doc_ids,
        "Shared document not found in search results",
    )
    assert_http_error(
        private_doc_id not in visible_doc_ids,
        "Private document incorrectly visible in search",
    )

    print("Document search visibility test passed")
    print("~" * 100)


def test_concurrent_document_access():
    print("Testing: Concurrent document access by multiple users")

    # Create test users
    users = [create_test_user(args.base_url) for _ in range(3)]

    # Create shared collection
    collection_id = create_test_collection(
        users[0].client, "Concurrent Access Collection"
    )

    # Add all users to collection
    for user in users[1:]:
        users[0].client.users.add_to_collection(user.user_id, collection_id)

    # Create shared document
    doc_content = f"Concurrent access document {uuid.uuid4()}"
    doc_id = create_test_document(
        users[0].client, doc_content, [collection_id]
    )

    # All users attempt to access document concurrently
    for user in users:
        try:
            doc = user.client.documents.retrieve(id=doc_id)["results"]
            assert_http_error(
                doc["id"] == doc_id,
                f"Concurrent access failed for user {user.email}",
            )
        except R2RException as e:
            print(f"Concurrent access failed for user {user.email}: {e}")
            sys.exit(1)

    print("Concurrent document access test passed")
    print("~" * 100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="R2R Multi-user Document Tests"
    )
    parser.add_argument("test_function", help="Test function to run")
    parser.add_argument(
        "--base-url",
        default="http://localhost:7272",
        help="Base URL for the R2R client",
    )
    args = parser.parse_args()

    test_function = args.test_function
    globals()[test_function]()
