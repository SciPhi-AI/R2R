from r2r import R2RClient


def test_agentic_citations_0(client: R2RClient, test_collection):

    response = client.retrieval.rag(
        query="Who was Aristotle? USE YOUR SOURCES.",
    )
    assert (
        response.results.citations[0].payload.document_id
        == test_collection["document_ids"][0]
    ), "Expected first citation to first doc"


def test_agentic_citations_1(client: R2RClient, test_collection):

    response = client.retrieval.rag(
        query="Who was Socrates? USE YOUR SOURCES.",
    )
    assert (
        response.results.citations[0].payload.document_id
        == test_collection["document_ids"][1]
    ), "Expected first citation to second doc"


def test_agentic_citations_2(client: R2RClient, test_collection):

    response = client.retrieval.rag(
        query="Who were Rene Descartes and Immanuel Kant? USE YOUR SOURCES.",
    )
    assert test_collection["document_ids"][2] in [
        citation.payload.document_id for citation in response.results.citations
    ], "Expected a citation to third doc"
    assert test_collection["document_ids"][3] in [
        citation.payload.document_id for citation in response.results.citations
    ], "Expected a citation to third doc"


def test_agentic_citations_3(client: R2RClient, test_collection):
    """
    Tests the agent endpoint in non-streaming mode with a single user message.
    Verifies final text and citations.
    """
    response = client.retrieval.agent(
        message={
            "role": "user",
            "content": "Tell me about Socrates in detail. USE YOUR SOURCES.",
        },
        rag_generation_config={
            "stream": False,
        },
    )
    # Typically returns a WrappedAgentResponse
    assert response.results.messages, "No messages returned"
    assistant_msg = response.results.messages[-1]
    assert "Socrates" in assistant_msg.content

    # If your server includes citations in `metadata`, you can check them here:
    if assistant_msg.metadata and "citations" in assistant_msg.metadata:
        citations = assistant_msg.metadata["citations"]
        print("citations = ", citations)
        doc_ids = [c["payload"]['document_id'] for c in citations]
        assert (
            str(test_collection["document_ids"][1]) in doc_ids
        ), "Expected Socrates doc citation"
