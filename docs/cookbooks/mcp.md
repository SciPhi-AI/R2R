The R2R Retrieval System is a Model Context Protocol (MCP) server that enhances Claude with retrieval and search capabilities. This server enables Claude to search through your knowledge base, perform vector searches, graph searches, web searches, and document searches, making it a powerful tool for retrieving relevant information.

## Features

- **Vector Search**: Find relevant text chunks based on semantic similarity
- **Graph Search**: Explore relationships between entities in your knowledge graph
- **Web Search**: Retrieve information from online sources
- **Document Search**: Access and query local context documents
- **RAG (Retrieval-Augmented Generation)**: Generate answers based on retrieved context

## Installation

### Prerequisites

- Claude Desktop (macOS or Windows)
- Node.js
- Python 3.6 or higher
- `mcp` Python package

### Local Installation

1. Install the R2R MCP server locally:

```bash
pip install mcp
mcp install r2r/mcp.py -v R2R_API_URL=http://localhost:7272
```

2. Start your local R2R API service at the specified URL.

### Cloud Installation

For cloud deployment, use your API key:

```bash
pip install mcp
mcp install r2r/mcp.py -v R2R_API_KEY=your_api_key_here
```

## Adding to Claude Desktop

**Note: This section is only necessary if the pip installation method fails.** In most cases, the pip installation above should be sufficient to make the R2R server available to Claude.

1. Open Claude Desktop and access the Settings:
   - On macOS: Click on the Claude menu and select "Settings..."
   - On Windows: Click on the Claude menu and select "Settings..."

2. In Settings, click on "Developer" in the left sidebar, then click "Edit Config"

3. Add the R2R server to your configuration file:

```json
{
  "mcpServers": {
    "r2r": {
      "command": "mcp",
      "args": ["run", "/my/path/to/R2R/py/r2r/mcp.py"]
    }
  }
}
```

4. Save the configuration file and restart Claude Desktop

5. After restarting, you should see the hammer icon in the bottom right corner of the input box, indicating that MCP tools are available

## Using the R2R Retrieval System

Once configured, Claude can automatically use the R2R tools when appropriate. You can also explicitly request Claude to use these tools:

- **Search**: Ask Claude to search your knowledge base with specific queries
  Example: "Search for information about vector databases in our documentation"

- **RAG**: Request Claude to generate answers based on retrieved context
  Example: "Use RAG to answer: What are the best practices for knowledge graph integration?"

## Available Tools

The R2R server provides two primary tools:

1. **search**: Performs retrieval operations and returns formatted results
   - Searches across vector, graph, web, and document sources
   - Returns source IDs and content for further reference

2. **rag**: Performs Retrieval-Augmented Generation
   - Retrieves relevant context and generates an answer
   - Provides a coherent response based on the knowledge base

## Example Outputs

When using the search tool, you'll receive structured results like:

```
Vector Search Results:
Source ID [abc1234]:
Text content from the vector search...

Graph Search Results:
Source ID [def5678]:
Entity Name: Sample Entity
Description: This is a description of the entity...

Web Search Results:
Source ID [ghi9012]:
Title: Sample Web Page
Link: https://example.com
Snippet: A snippet from the web page...

Local Context Documents:
Full Document ID: jkl3456...
Shortened Document ID: jkl3456
Document Title: Sample Document
Summary: A summary of the document...

Chunk ID abc1234:
Text content from the document chunk...
```

## Troubleshooting

- If the server doesn't appear in Claude, check that the configuration file is formatted correctly
- Ensure that the R2R service is running at the specified URL for local installations
- Verify that your API key is valid for cloud installations
- Check the Claude Desktop logs for any error messages

## Next Steps

- Explore other MCP servers that can be integrated with Claude
- Consider building custom tools to extend the R2R functionality
- Contribute to the MCP community by sharing your experiences and use cases

---

For more information on MCP and its capabilities, refer to the official MCP documentation. For specific questions about the R2R Retrieval System, please contact your system administrator or developer.
