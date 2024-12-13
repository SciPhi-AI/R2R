import argparse
import random
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Optional

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
    user = client.users.create(email, password)["results"]
    client.users.login(email, password)

    return TestUser(
        email=email, password=password, client=client, user_id=user["id"]
    )


def create_test_document(
    client: R2RClient, content: str, collection_ids: list[str] = None
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

    client = R2RClient(args.base_url)
    # Create two test users
    # user1 = create_test_user(args.base_url)
    # user2 = create_test_user(args.base_url)
    import random

    f1 = random.randint(1, 1_000_000)
    f2 = random.randint(1, 1_000_000)
    client.users.create(f"user2_{f2}@test.com", "password123")
    client.users.login(f"user2_{f2}@test.com", "password123")
    user2_id = client.users.me()["results"]["id"]
    client.users.logout()
    print("user2_id = ", user2_id)

    client.users.create(f"user1_{f1}@test.com", "password123")
    client.users.login(f"user1_{f1}@test.com", "password123")
    user1_id = client.users.me()["results"]["id"]
    print("user1_id = ", user1_id)

    # User1 creates a collection
    print("creating collection")
    collection_id = create_test_collection(client, "Shared Collection")
    print("collection_id = ", collection_id)
    client.users.login(f"user1_{f1}@test.com", "password123")

    doc_content = f"Shared document content {uuid.uuid4()}"
    doc_id = create_test_document(client, doc_content, [collection_id])
    print("doc_id = ", doc_id)
    client.collections.add_user(collection_id, user2_id)
    client.users.logout()

    available_documents = client.collections.list_documents(collection_id)[
        "results"
    ]
    print("available_documents = ", available_documents)

    # Verify user2 can access the document
    try:
        client.users.login(f"user2_{f2}@test.com", "password123")
        print("retrieving doc...")
        doc = client.documents.retrieve(id=doc_id)["results"]
        print("doc = ", doc)
        assert_http_error(
            doc["id"] == doc_id, "User2 couldn't access shared document"
        )
    except R2RException as e:
        print(f"User2 failed to access shared document: {e}")
        sys.exit(1)

    print("Document sharing via collections test passed")
    print("~" * 100)


def test_collection_document_removal():
    print("Testing: Document access after collection removal")

    client = R2RClient(args.base_url)

    # Create two test users with random IDs
    f1 = random.randint(1, 1_000_000)
    f2 = random.randint(1, 1_000_000)

    # Create and get user2 first
    client.users.create(f"user2_{f2}@test.com", "password123")
    client.users.login(f"user2_{f2}@test.com", "password123")
    user2_id = client.users.me()["results"]["id"]
    client.users.logout()
    print("user2_id = ", user2_id)

    # Create and login as user1
    client.users.create(f"user1_{f1}@test.com", "password123")
    client.users.login(f"user1_{f1}@test.com", "password123")
    user1_id = client.users.me()["results"]["id"]
    print("user1_id = ", user1_id)

    # User1 creates a collection
    print("creating collection")
    collection_id = create_test_collection(client, "Temporary Collection")
    print("collection_id = ", collection_id)

    # Ensure user1 is logged in
    client.users.login(f"user1_{f1}@test.com", "password123")

    # Create document in collection
    doc_content = f"Collection document content {uuid.uuid4()}"
    doc_id = create_test_document(client, doc_content, [collection_id])
    print("doc_id = ", doc_id)

    # Add user2 to collection using collections API
    client.collections.add_user(collection_id, user2_id)
    client.users.logout()

    # Verify user2 can access document
    try:
        client.users.login(f"user2_{f2}@test.com", "password123")
        print("retrieving doc...")
        doc = client.documents.retrieve(id=doc_id)["results"]
        print("doc = ", doc)
        assert_http_error(
            doc["id"] == doc_id, "User2 couldn't access shared document"
        )
    except R2RException as e:
        print(f"User2 failed to access shared document: {e}")
        sys.exit(1)

    # Log back in as user1 to remove user2
    client.users.login(f"user1_{f1}@test.com", "password123")
    client.collections.remove_user(collection_id, user2_id)
    client.users.logout()

    # Verify user2 can no longer access the document
    try:
        client.users.login(f"user2_{f2}@test.com", "password123")
        client.documents.retrieve(id=doc_id)
        # print("Expected 403 after collection removal")
        sys.exit(1)
    except R2RException as e:
        pass
        # assert_http_error(
        #     e.status_code == 403,
        #     "Wrong error code after collection removal"
        # )

    print("Collection document removal test passed")
    print("~" * 100)


def test_document_access_restrictions():
    print("Testing: Document access restrictions between users")

    client = R2RClient(args.base_url)

    # Create two test users with random IDs
    f1 = random.randint(1, 1_000_000)
    f2 = random.randint(1, 1_000_000)

    # Create and get user2 first
    client.users.create(f"user2_{f2}@test.com", "password123")
    client.users.login(f"user2_{f2}@test.com", "password123")
    user2_id = client.users.me()["results"]["id"]
    client.users.logout()

    # Create and login as user1
    client.users.create(f"user1_{f1}@test.com", "password123")
    client.users.login(f"user1_{f1}@test.com", "password123")
    user1_id = client.users.me()["results"]["id"]

    # User1 creates a private document
    doc_content = f"Private document content {uuid.uuid4()}"
    doc_id = create_test_document(client, doc_content)
    client.users.logout()

    # Verify user2 cannot access the document
    try:
        client.users.login(f"user2_{f2}@test.com", "password123")
        client.documents.retrieve(id=doc_id)
        print("Expected 403 for accessing private document")
        sys.exit(1)
    except R2RException as e:
        pass
        # assert_http_error(
        #     e.status_code == 403,
        #     "Wrong error code for unauthorized document access"
        # )

    print("Document access restrictions test passed")
    print("~" * 100)


def test_document_search_across_users():
    print("Testing: Document search visibility across users")

    client = R2RClient(args.base_url)

    # Create two test users with random IDs
    f1 = random.randint(1, 1_000_000)
    f2 = random.randint(1, 1_000_000)

    # Create and get user2 first
    client.users.create(f"user2_{f2}@test.com", "password123")
    client.users.login(f"user2_{f2}@test.com", "password123")
    user2_id = client.users.me()["results"]["id"]
    client.users.logout()

    # Create and login as user1
    client.users.create(f"user1_{f1}@test.com", "password123")
    client.users.login(f"user1_{f1}@test.com", "password123")
    user1_id = client.users.me()["results"]["id"]

    # Create unique search term
    search_term = f"unique_term_{uuid.uuid4()}"

    # User1 creates private document
    doc1_content = f"Private document with {search_term}"
    private_doc_id = create_test_document(client, doc1_content)

    # Create shared collection and document
    collection_id = create_test_collection(client, "Search Test Collection")
    doc2_content = f"Shared document with {search_term}"
    shared_doc_id = create_test_document(client, doc2_content, [collection_id])

    # Add user2 to collection
    client.collections.add_user(collection_id, user2_id)
    client.users.logout()

    # Wait for search indexing
    time.sleep(1)

    # User2 searches for documents
    client.users.login(f"user2_{f2}@test.com", "password123")
    search_results = client.documents.search(
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

    client = R2RClient(args.base_url)
    user_ids = []
    credentials = []

    # Create three users with random IDs
    for i in range(3):
        f = random.randint(1, 1_000_000)
        client.users.create(f"user{i}_{f}@test.com", "password123")
        client.users.login(f"user{i}_{f}@test.com", "password123")
        user_ids.append(client.users.me()["results"]["id"])
        credentials.append((f"user{i}_{f}@test.com", "password123"))
        client.users.logout()

    # Login as first user to create collection
    client.users.login(credentials[0][0], credentials[0][1])

    # Create shared collection
    collection_id = create_test_collection(
        client, "Concurrent Access Collection"
    )

    # Add other users to collection
    for user_id in user_ids[1:]:
        client.collections.add_user(collection_id, user_id)

    # Create shared document
    doc_content = f"Concurrent access document {uuid.uuid4()}"
    doc_id = create_test_document(client, doc_content, [collection_id])
    client.users.logout()

    # All users attempt to access document concurrently
    for i, (email, password) in enumerate(credentials):
        try:
            client.users.login(email, password)
            doc = client.documents.retrieve(id=doc_id)["results"]
            assert_http_error(
                doc["id"] == doc_id,
                f"Concurrent access failed for user {email}",
            )
            client.users.logout()
        except R2RException as e:
            print(f"Concurrent access failed for user {email}: {e}")
            sys.exit(1)

    print("Concurrent document access test passed")
    print("~" * 100)


def test_multiple_collections_document_access():
    print(
        "Testing: Document in multiple collections and user access after partial removal"
    )

    # Create a user (owner) and two collections
    owner_email = f"owner_{uuid.uuid4()}@test.com"
    owner_password = "password"
    client = R2RClient(args.base_url)

    client.users.create(owner_email, owner_password)
    client.users.login(owner_email, owner_password)

    coll1 = client.collections.create(name="Collection One")["results"]["id"]
    coll2 = client.collections.create(name="Collection Two")["results"]["id"]

    # Create a document and add it to both collections
    doc_id = client.documents.create(
        raw_text="Shared doc", run_with_orchestration=False
    )["results"]["document_id"]
    client.collections.add_document(coll1, doc_id)
    client.collections.add_document(coll2, doc_id)

    # Create another user and add to both collections
    other_email = f"other_{uuid.uuid4()}@test.com"
    other_password = "password123"
    client.users.logout()
    client.users.create(other_email, other_password)
    client.users.login(other_email, other_password)
    other_user_id = client.users.me()["results"]["id"]
    client.users.logout()

    # Owner re-login and add user to both collections
    client.users.login(owner_email, owner_password)
    client.collections.add_user(coll1, other_user_id)
    client.collections.add_user(coll2, other_user_id)
    client.users.logout()

    # User should have access now
    client.users.login(other_email, other_password)
    # Ensure the user can retrieve the doc
    retrieved_doc = client.documents.retrieve(doc_id)["results"]
    assert_http_error(
        retrieved_doc["id"] == doc_id,
        "User cannot access shared doc initially",
    )
    client.users.logout()

    # Owner removes user from one collection only
    client.users.login(owner_email, owner_password)
    client.collections.remove_user(coll1, other_user_id)
    client.users.logout()

    # User still belongs to coll2 with this doc, should still have access
    client.users.login(other_email, other_password)
    retrieved_doc_again = client.documents.retrieve(doc_id)["results"]
    assert_http_error(
        retrieved_doc_again["id"] == doc_id, "User lost access prematurely"
    )
    client.users.logout()

    # Now owner removes user from the second collection
    client.users.login(owner_email, owner_password)
    client.collections.remove_user(coll2, other_user_id)
    client.users.logout()

    # User tries again
    client.users.login(other_email, other_password)
    try:
        response = client.documents.retrieve(doc_id)
        print("response =", response)
        print(
            "Expected 403 after user removed from all collections containing the doc."
        )
        sys.exit(1)
    except R2RException as e:
        print("e = ", e)
        assert_http_error(
            e.status_code == 403,
            "Wrong error code after final collection removal",
        )

    print("Multiple collections document access test passed")
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
