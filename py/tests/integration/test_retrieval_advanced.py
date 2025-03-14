import uuid

from r2r import R2RClient


# Semantic Search Tests
def test_semantic_search_with_near_duplicates(client: R2RClient):
    """Test semantic search can handle and differentiate near-duplicate
    content."""
    random_1 = str(uuid.uuid4())
    random_2 = str(uuid.uuid4())
    # Create two similar but distinct documents
    doc1 = client.documents.create(
        raw_text=
        f"Aristotle was a Greek philosopher who studied logic {random_1}."
    ).results.document_id
    doc2 = client.documents.create(
        raw_text=
        f"Aristotle, the Greek philosopher, studied formal logic {random_2}."
    ).results.document_id

    resp = client.retrieval.search(
        query="Tell me about Aristotle's work in logic",
        search_mode="custom",
        search_settings={
            "use_semantic_search": True,
            "limit": 25
        },
    )
    results = resp.results.chunk_search_results

    # Both documents should be returned but with different scores
    scores = [
        r.score for r in results
        if str(r.document_id) in [str(doc1), str(doc2)]
    ]
    assert len(scores) == 2, "Expected both similar documents"
    assert len(
        set(scores)) == 2, ("Expected different scores for similar documents")


def test_semantic_search_multilingual(client: R2RClient):
    """Test semantic search handles multilingual content."""
    # Create documents in different languages
    random_1 = str(uuid.uuid4())
    random_2 = str(uuid.uuid4())
    random_3 = str(uuid.uuid4())

    docs = [
        (f"Aristotle was a philosopher {random_1}", "English"),
        (f"Aristóteles fue un filósofo {random_2}", "Spanish"),
        (f"アリストテレスは哲学者でした {random_3}", "Japanese"),
    ]
    doc_ids = []
    for text, lang in docs:
        doc_id = client.documents.create(raw_text=text,
                                         metadata={
                                             "language": lang
                                         }).results.document_id
        doc_ids.append(doc_id)

    # Query in different languages
    queries = [
        "Who was Aristotle?",
        "¿Quién fue Aristóteles?",
        "アリストテレスとは誰でしたか？",
    ]

    for query in queries:
        resp = client.retrieval.search(
            query=query,
            search_mode="custom",
            search_settings={
                "use_semantic_search": True,
                "limit": len(doc_ids),
            },
        )
        results = resp.results.chunk_search_results
        assert len(results) > 0, f"No results found for query: {query}"


# UNCOMMENT LATER
# # Hybrid Search Tests
# def test_hybrid_search_weight_balance(client: R2RClient):
#     """Test hybrid search balances semantic and full-text scores appropriately"""
#     # Create a document with high semantic relevance but low keyword match
#     semantic_doc = client.documents.create(
#         raw_text="The ancient Greek thinker who studied under Plato made significant contributions to logic."
#     ).results.document_id

#     # Create a document with high keyword match but low semantic relevance
#     keyword_doc = client.documents.create(
#         raw_text="Aristotle is a common name in certain regions. This text mentions Aristotle but is not about philosophy."
#     ).results.document_id

#     resp = client.retrieval.search(
#         query="What were Aristotle's philosophical contributions?",
#         search_mode="custom",
#         search_settings={
#             "use_hybrid_search": True,
#             "hybrid_settings": {
#                 "semantic_weight": 0.7,
#                 "full_text_weight": 0.3,
#             },
#         },
#     )
#     results = resp["results"]["chunk_search_results"]

#     # The semantic document should rank higher
#     semantic_rank = next(
#         i for i, r in enumerate(results) if r["document_id"] == semantic_doc
#     )
#     keyword_rank = next(
#         i for i, r in enumerate(results) if r["document_id"] == keyword_doc
#     )
#     assert (
#         semantic_rank < keyword_rank
#     ), "Semantic relevance should outweigh keyword matches"


# RAG Tests
def test_rag_context_window_limits(client: R2RClient):
    """Test RAG handles documents at or near context window limits."""
    # Create a document that approaches the context window limit
    random_1 = str(uuid.uuid4())
    large_text = ("Aristotle " * 1000
                  )  # Adjust multiplier based on your context window
    doc_id = client.documents.create(
        raw_text=f"{large_text} {random_1}").results.document_id

    resp = client.retrieval.rag(
        query="Summarize this text about Aristotle",
        search_settings={"filters": {
            "document_id": {
                "$eq": str(doc_id)
            }
        }},
        rag_generation_config={"max_tokens": 100},
    )
    assert resp.results is not None, (
        "RAG should handle large context gracefully")


# UNCOMMENT LATER
# def test_rag_empty_chunk_handling(client: R2RClient):
#     """Test RAG properly handles empty or whitespace-only chunks"""
#     doc_id = client.documents.create(chunks=["", " ", "\n", "Valid content"])[
#         "results"
#     ]["document_id"]

#     resp = client.retrieval.rag(
#         query="What is the content?",
#         search_settings={"filters": {"document_id": {"$eq": str(doc_id)}}},
#     )
#     assert "results" in resp, "RAG should handle empty chunks gracefully"

# # Agent Tests
# def test_agent_clarification_requests(client: R2RClient):
#     """Test agent's ability to request clarification for ambiguous queries"""
#     msg = Message(role="user", content="Compare them")
#     resp = client.retrieval.agent(
#         message=msg,
#         search_settings={"use_semantic_search": True},
#     )
#     content = resp["results"]["messages"][-1]["content"]
#     assert any(
#         phrase in content.lower()
#         for phrase in [
#             "could you clarify",
#             "who do you",
#             "what would you",
#             "please specify",
#         ]
#     ), "Agent should request clarification for ambiguous queries"

## TODO - uncomment later
# def test_agent_source_citation_consistency(client: R2RClient):
#     """Test agent consistently cites sources across conversation turns"""
#     conversation_id = client.conversations.create()["results"]["id"]

#     # First turn - asking about a specific topic
#     msg1 = Message(role="user", content="What did Aristotle say about ethics?")
#     resp1 = client.retrieval.agent(
#         message=msg1,
#         conversation_id=conversation_id,
#         include_title_if_available=True,
#     )

#     # Second turn - asking for more details
#     msg2 = Message(role="user", content="Can you elaborate on that point?")
#     resp2 = client.retrieval.agent(
#         message=msg2,
#         conversation_id=conversation_id,
#         include_title_if_available=True,
#     )

#     # Check that sources are consistently cited across turns
#     sources1 = _extract_sources(resp1["results"]["messages"][-1]["content"])
#     sources2 = _extract_sources(resp2["results"]["messages"][-1]["content"])
#     assert (
#         len(sources1) > 0 and len(sources2) > 0
#     ), "Both responses should cite sources"
#     assert any(
#         s in sources2 for s in sources1
#     ), "Follow-up should reference some original sources"

## TODO - uncomment later
# # Error Handling Tests
# def test_malformed_filter_handling(client: R2RClient):
#     """Test system properly handles malformed filter conditions"""
#     invalid_filters = [
#         {"$invalid": {"$eq": "value"}},
#         {"field": {"$unsupported": "value"}},
#         {"$and": [{"field": "incomplete_operator"}]},
#         {"$or": []},  # Empty OR condition
#         {"$and": [{}]},  # Empty filter in AND
#     ]

#     for invalid_filter in invalid_filters:
#         with pytest.raises(R2RException) as exc_info:
#             client.retrieval.search(
#                 query="test", search_settings={"filters": invalid_filter}
#             )
#         assert exc_info.value.status_code in [
#             400,
#             422,
#         ], f"Expected validation error for filter: {invalid_filter}"

## TODO - Uncomment later
# def test_concurrent_search_stability(client: R2RClient):
#     """Test system handles concurrent search requests properly"""
#     import asyncio

#     async def concurrent_searches():
#         tasks = []
#         for i in range(10):  # Adjust number based on system capabilities
#             task = asyncio.create_task(
#                 client.retrieval.search_async(
#                     query=f"Concurrent test query {i}", search_mode="basic"
#                 )
#             )
#             tasks.append(task)

#         results = await asyncio.gather(*tasks, return_exceptions=True)
#         return results

#     results = asyncio.run(concurrent_searches())
#     assert all(
#         not isinstance(r, Exception) for r in results
#     ), "Concurrent searches should complete without errors"


# Helper function for source extraction
def _extract_sources(content: str) -> list[str]:
    """Extract source citations from response content."""
    # This is a simplified version - implement based on your citation format
    import re

    return re.findall(r'"([^"]*)"', content)
