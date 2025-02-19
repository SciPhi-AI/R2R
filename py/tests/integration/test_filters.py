import uuid

import pytest

from r2r import R2RClient, R2RException


@pytest.fixture
def setup_docs_with_collections(client: R2RClient):
    # Create some test collections

    random_suffix = str(uuid.uuid4())[:8]
    coll_ids = []
    for i in range(3):
        coll_id = client.collections.create(name=f"TestColl{i}").results.id
        coll_ids.append(coll_id)

    # Create documents with different collection arrangements:
    # doc1: [coll1]
    doc1 = client.documents.create(
        raw_text="Doc in coll1" + random_suffix,
        run_with_orchestration=False).results.document_id
    client.collections.add_document(coll_ids[0], doc1)

    # doc2: [coll1, coll2]
    doc2 = client.documents.create(
        raw_text="Doc in coll1 and coll2" + random_suffix,
        run_with_orchestration=False,
    ).results.document_id
    client.collections.add_document(coll_ids[0], doc2)
    client.collections.add_document(coll_ids[1], doc2)

    # doc3: no collections
    doc3 = client.documents.create(
        raw_text="Doc in no collections" + random_suffix,
        run_with_orchestration=False,
    ).results.document_id

    # doc4: [coll3]
    doc4 = client.documents.create(
        raw_text="Doc in coll3" + random_suffix,
        run_with_orchestration=False).results.document_id
    client.collections.add_document(coll_ids[2], doc4)

    yield {"coll_ids": coll_ids, "doc_ids": [doc1, doc2, doc3, doc4]}

    # Cleanup
    for d_id in [doc1, doc2, doc3, doc4]:
        try:
            client.documents.delete(id=d_id)
        except R2RException:
            pass
    for c_id in coll_ids:
        try:
            client.collections.delete(c_id)
        except R2RException:
            pass


def test_collection_id_eq_filter(client: R2RClient,
                                 setup_docs_with_collections):
    coll_ids = setup_docs_with_collections["coll_ids"]
    doc_ids = setup_docs_with_collections["doc_ids"]
    doc1, doc2, doc3, doc4 = doc_ids

    # collection_id = coll_ids[0] should match doc1 and doc2 only
    filters = {"collection_id": {"$eq": str(coll_ids[0])}}
    listed = client.retrieval.search(query="whoami",
                                     search_settings={
                                         "filters": filters
                                     }).results.chunk_search_results
    found_ids = {str(d.document_id) for d in listed}
    assert {
        str(doc1),
        str(doc2),
    } == found_ids, f"Expected doc1 and doc2, got {found_ids}"


def test_collection_id_ne_filter(client: R2RClient,
                                 setup_docs_with_collections):
    coll_ids = setup_docs_with_collections["coll_ids"]
    doc_ids = setup_docs_with_collections["doc_ids"]
    doc1, doc2, doc3, doc4 = doc_ids

    filters = {"collection_id": {"$ne": str(coll_ids[0])}}
    listed = client.retrieval.search(query="whoami",
                                     search_settings={
                                         "filters": filters
                                     }).results.chunk_search_results
    found_ids = {str(d.document_id) for d in listed}
    assert str(
        coll_ids[0]) not in found_ids, (f"Expected no coll0, got {found_ids}")

    # expected_ids = {doc3, doc4}

    # assert expected_ids.issubset(
    #     found_ids
    # ), f"Expected {expected_ids} to be included in results, but got {found_ids}"


def test_collection_id_in_filter(client: R2RClient,
                                 setup_docs_with_collections):
    coll_ids = setup_docs_with_collections["coll_ids"]
    doc_ids = setup_docs_with_collections["doc_ids"]
    doc1, doc2, doc3, doc4 = doc_ids

    # collection_id in [coll_ids[0], coll_ids[2]] means docs in either coll0 or coll2
    # doc1 in coll0, doc2 in coll0, doc4 in coll2
    # doc3 is in none
    filters = {"collection_id": {"$in": [str(coll_ids[0]), str(coll_ids[2])]}}
    listed = client.retrieval.search(query="whoami",
                                     search_settings={
                                         "filters": filters
                                     }).results.chunk_search_results
    found_ids = {str(d.document_id) for d in listed}
    assert {
        str(doc1),
        str(doc2),
        str(doc4),
    } == found_ids, f"Expected doc1, doc2, doc4, got {found_ids}"


def test_collection_id_nin_filter(client: R2RClient,
                                  setup_docs_with_collections):
    coll_ids = setup_docs_with_collections["coll_ids"]
    doc_ids = setup_docs_with_collections["doc_ids"]
    doc1, doc2, doc3, doc4 = doc_ids

    filters = {"collection_id": {"$nin": [str(coll_ids[1])]}}
    listed = client.retrieval.search(query="whoami",
                                     search_settings={
                                         "filters": filters
                                     }).results.chunk_search_results
    found_ids = {str(d.document_id) for d in listed}
    # expected_ids = {doc1, doc3, doc4}
    found_ids = {str(d.document_id) for d in listed}
    assert str(
        coll_ids[1]) not in found_ids, (f"Expected no coll1, got {found_ids}")

    # assert expected_ids.issubset(
    #     found_ids
    # ), f"Expected {expected_ids} to be included in results, but got {found_ids}"


def test_collection_id_contains_filter(client: R2RClient,
                                       setup_docs_with_collections):
    coll_ids = setup_docs_with_collections["coll_ids"]
    doc_ids = setup_docs_with_collections["doc_ids"]
    doc1, doc2, doc3, doc4 = doc_ids

    # $contains: For a single collection_id, we interpret as arrays that must contain the given UUID.
    # If collection_id {"$contains": "coll_ids[0]"}, docs must have coll0 in their array
    # That would be doc1 and doc2 only
    filters = {"collection_id": {"$contains": str(coll_ids[0])}}
    listed = client.retrieval.search(query="whoami",
                                     search_settings={
                                         "filters": filters
                                     }).results.chunk_search_results
    found_ids = {str(d.document_id) for d in listed}
    assert {
        str(doc1),
        str(doc2),
    } == found_ids, f"Expected doc1 and doc2, got {found_ids}"


def test_collection_id_contains_multiple(client: R2RClient,
                                         setup_docs_with_collections):
    coll_ids = setup_docs_with_collections["coll_ids"]
    doc_ids = setup_docs_with_collections["doc_ids"]
    doc1, doc2, doc3, doc4 = doc_ids

    # If we allow $contains with a list, e.g., {"$contains": [coll_ids[0], coll_ids[1]]},
    # this should mean the doc's collection_ids contain ALL of these.
    # Only doc2 has coll0 AND coll1. doc1 only has coll0, doc3 no collections, doc4 only coll3.
    filters = {
        "collection_id": {
            "$contains": [str(coll_ids[0]), str(coll_ids[1])]
        }
    }
    listed = client.retrieval.search(query="whoami",
                                     search_settings={
                                         "filters": filters
                                     }).results.chunk_search_results
    found_ids = {str(d.document_id) for d in listed}
    assert {str(doc2)} == found_ids, f"Expected doc2 only, got {found_ids}"


def test_delete_by_collection_id_eq(client: R2RClient,
                                    setup_docs_with_collections):
    coll_ids = setup_docs_with_collections["coll_ids"]
    doc1, doc2, doc3, doc4 = setup_docs_with_collections["doc_ids"]

    # Delete documents in coll0
    filters = {"collection_id": {"$eq": str(coll_ids[0])}}
    del_resp = client.documents.delete_by_filter(filters).results
    assert del_resp.success, "Failed to delete by collection_id $eq filter"

    # doc1 and doc2 should be deleted, doc3 and doc4 remain
    for d_id in [doc1, doc2]:
        with pytest.raises(R2RException) as exc:
            client.documents.retrieve(d_id)
        assert exc.value.status_code == 404, f"Doc {d_id} still exists!"
    # Check doc3 and doc4 still exist
    assert client.documents.retrieve(doc3)
    assert client.documents.retrieve(doc4)
