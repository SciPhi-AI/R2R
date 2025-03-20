# Add to your local machine with `mcp install r2r/mcp.py -v R2R_API_URL=http://localhost:7272` or so.
from r2r import R2RClient


def id_to_shorthand(id: str) -> str:
    return str(id)[:7]


def format_search_results_for_llm(
    results,
) -> str:
    """
    Instead of resetting 'source_counter' to 1, we:
     - For each chunk / graph / web / doc in `results`,
     - Find the aggregator index from the collector,
     - Print 'Source [X]:' with that aggregator index.
    """
    lines = []

    # We'll build a quick helper to locate aggregator indices for each object:
    # Or you can rely on the fact that we've added them to the collector
    # in the same order. But let's do a "lookup aggregator index" approach:

    # 1) Chunk search
    if results.chunk_search_results:
        lines.append("Vector Search Results:")
        for c in results.chunk_search_results:
            lines.append(f"Source ID [{id_to_shorthand(c.id)}]:")
            lines.append(c.text or "")  # or c.text[:200] to truncate

    # 2) Graph search
    if results.graph_search_results:
        lines.append("Graph Search Results:")
        for g in results.graph_search_results:
            lines.append(f"Source ID [{id_to_shorthand(g.id)}]:")
            if hasattr(g.content, "summary"):
                lines.append(f"Community Name: {g.content.name}")
                lines.append(f"ID: {g.content.id}")
                lines.append(f"Summary: {g.content.summary}")
                # etc. ...
            elif hasattr(g.content, "name") and hasattr(
                g.content, "description"
            ):
                lines.append(f"Entity Name: {g.content.name}")
                lines.append(f"Description: {g.content.description}")
            elif (
                hasattr(g.content, "subject")
                and hasattr(g.content, "predicate")
                and hasattr(g.content, "object")
            ):
                lines.append(
                    f"Relationship: {g.content.subject}-{g.content.predicate}-{g.content.object}"
                )
            # Add metadata if needed

    # 3) Web search
    if results.web_search_results:
        lines.append("Web Search Results:")
        for w in results.web_search_results:
            lines.append(f"Source ID [{id_to_shorthand(w.id)}]:")
            lines.append(f"Title: {w.title}")
            lines.append(f"Link: {w.link}")
            lines.append(f"Snippet: {w.snippet}")

    # 4) Local context docs
    if results.document_search_results:
        lines.append("Local Context Documents:")
        for doc_result in results.document_search_results:
            doc_title = doc_result.title or "Untitled Document"
            doc_id = doc_result.id
            summary = doc_result.summary

            lines.append(f"Full Document ID: {doc_id}")
            lines.append(f"Shortened Document ID: {id_to_shorthand(doc_id)}")
            lines.append(f"Document Title: {doc_title}")
            if summary:
                lines.append(f"Summary: {summary}")

            if doc_result.chunks:
                # Then each chunk inside:
                for chunk in doc_result.chunks:
                    lines.append(
                        f"\nChunk ID {id_to_shorthand(chunk['id'])}:\n{chunk['text']}"
                    )

    result = "\n".join(lines)
    return result


# Create a FastMCP server

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("R2R Retrieval System")
except Exception as e:
    raise ImportError(
        "MCP is not installed. Please run `pip install mcp`"
    ) from e

# Pass lifespan to server
mcp = FastMCP("R2R Retrieval System")


# RAG query tool
@mcp.tool()
async def search(query: str) -> str:
    """
    Performs a

    Args:
        query: The question to answer using the knowledge base

    Returns:
        A response generated based on relevant context from the knowledge base
    """
    client = R2RClient()

    # Call the RAG endpoint
    search_response = client.retrieval.search(
        query=query,
    )
    return format_search_results_for_llm(search_response.results)


# RAG query tool
@mcp.tool()
async def rag(query: str) -> str:
    """
    Perform a Retrieval-Augmented Generation query

    Args:
        query: The question to answer using the knowledge base

    Returns:
        A response generated based on relevant context from the knowledge base
    """
    client = R2RClient()

    # Call the RAG endpoint
    rag_response = client.retrieval.rag(
        query=query,
    )

    return rag_response.results.generated_answer  # type: ignore


# Run the server if executed directly
if __name__ == "__main__":
    mcp.run()
