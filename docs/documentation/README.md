# Getting Started with R2R

This guide will walk you through setting up R2R and using its core features to build AI-powered document understanding applications.

**On this page**
1. [Create an Account](#create-an-account)
2. [Install the SDK](#install-the-sdk)
3. [Environment Setup](#environment-setup)
4. [Initialize the Client](#initialize-the-client)
5. [Ingesting Files](#ingesting-files)
6. [Getting File Status](#getting-file-status)
7. [Executing a Search](#executing-a-search)
8. [RAG (Retrieval-Augmented Generation)](#rag-retrieval-augmented-generation)
9. [Streaming RAG](#streaming-rag)
10. [Streaming Agentic RAG](#streaming-agentic-rag)
11. [Additional Features](#additional-features)
12. [Next Steps](#next-steps)

## Create an Account

> **Note**: For those interested in deploying R2R locally, please refer to our [local installation guide](../self-hosting/getting-started/installation/overview.md).

## Install the SDK

R2R offers Python and JavaScript SDKs to interact with the system.

### Python
```bash
pip install r2r
```

### JavaScript
```bash
npm i r2r-js
```

## Initialize the Client

### Python
```python
# export R2R_API_KEY=...
from r2r import R2RClient

client = R2RClient() # can set remote w/ R2RClient(base_url=...)

# or, alternatively, client.users.login("my@email.com", "my_strong_password")
```

### JavaScript
```javascript
// export R2R_API_KEY=...
const { r2rClient } = require('r2r-js');

const client = new r2rClient(); // can set baseURL=...

// or, alternatively, client.users.login("my@email.com", "my_strong_password")
```

## Ingesting Files

When you ingest files into R2R, the server accepts the task, processes and chunks the file, and generates a summary of the document.

### Python
```python
client.documents.create_sample(hi_res=True)
# to ingest your own document, client.documents.create(file_path="/path/to/file")
```

### JavaScript
```javascript
client.documents.createSample({ ingestionMode: "hi-res" })
// to ingest your own document, client.documents.create({filePath: </path/to/file>})
```

Example output:
```plaintext
IngestionResponse(message='Document created and ingested successfully.', task_id=None, document_id=UUID('e43864f5-a36f-548e-aacd-6f8d48b30c7f'))
```

## Getting File Status

After file ingestion is complete, you can check the status of your documents by listing them.

### Python
```python
client.documents.list()
```

### JavaScript
```javascript
client.documents.list()
```

### cURL
```bash
curl -X GET http://localhost:7272/v3/documents \
  -H "Content-Type: application/json"
```

Example output:
```plaintext
[
  DocumentResponse(
    id=UUID('e43864f5-a36f-548e-aacd-6f8d48b30c7f'),
    collection_ids=[UUID('122fdf6a-e116-546b-a8f6-e4cb2e2c0a09')],
    owner_id=UUID('2acb499e-8428-543b-bd85-0d9098718220'),
    document_type=<DocumentType.PDF: 'pdf'>,
    metadata={'title': 'DeepSeek_R1.pdf', 'version': 'v0'},
    version='v0',
    size_in_bytes=1768572,
    ingestion_status=<IngestionStatus.SUCCESS: 'success'>,
    extraction_status=<GraphExtractionStatus.PENDING: 'pending'>,
    created_at=datetime.datetime(2025, 2, 8, 3, 31, 39, 126759, tzinfo=TzInfo(UTC)),
    updated_at=datetime.datetime(2025, 2, 8, 3, 31, 39, 160114, tzinfo=TzInfo(UTC)),
    ingestion_attempt_number=None,
    summary="The document contains a comprehensive overview of DeepSeek-R1...",
    summary_embedding=None,
    total_tokens=29673
  ), ...
]
```

## Executing a Search

Perform a search query:

### Python
```python
client.retrieval.search(
  query="What is DeepSeek R1?",
)
```

### JavaScript
```javascript
client.retrieval.search({
  query: "What is DeepSeek R1?",
})
```

### cURL
```bash
curl -X POST http://localhost:7272/v3/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is DeepSeek R1?"
  }'
```

The search query will use basic similarity search to find the most relevant documents. You can use advanced search methods like [hybrid search](../documentation/retrieval/hybrid-search.md) or [graph search](../documentation/general/graphs.md) depending on your use case.

Example output:
```plaintext
AggregateSearchResult(
  chunk_search_results=[
    ChunkSearchResult(
      score=0.643,
      text="Document Title: DeepSeek_R1.pdf
      Text: could achieve an accuracy of over 70%.
      DeepSeek-R1 also delivers impressive results on IF-Eval..."
    ), ...
  ],
  graph_search_results=[],
  web_search_results=[],
  context_document_results=[]
)
```

## RAG (Retrieval-Augmented Generation)

Generate a RAG response:

### Python
```python
client.retrieval.rag(
  query="What is DeepSeek R1?",
)
```

### JavaScript
```javascript
client.retrieval.rag({
  query: "What is DeepSeek R1?",
})
```

### cURL
```bash
curl -X POST http://localhost:7272/v3/retrieval/rag \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is DeepSeek R1?"
  }'
```

Example output:
```plaintext
RAGResponse(
  generated_answer='DeepSeek-R1 is a model that demonstrates impressive performance across various tasks, leveraging reinforcement learning (RL) and supervised fine-tuning (SFT) to enhance its capabilities...',
  search_results=AggregateSearchResult(...),
  citations=[Citation(id='cit_3a35e39', object='citation', ...)],
  metadata={...}
)
```

## Streaming RAG

Generate a streaming RAG response:

### Python
```python
from r2r import (
    CitationEvent,
    FinalAnswerEvent,
    MessageEvent,
    SearchResultsEvent,
    R2RClient,
)

result_stream = client.retrieval.rag(
    query="What is DeepSeek R1?",
    search_settings={"limit": 25},
    rag_generation_config={"stream": True},
)

# can also do a switch on `type` field
for event in result_stream:
    if isinstance(event, SearchResultsEvent):
        print("Search results:", event.data)
    elif isinstance(event, MessageEvent):
        print("Partial message:", event.data.delta)
    elif isinstance(event, CitationEvent):
        print("New citation detected:", event.data)
    elif isinstance(event, FinalAnswerEvent):
        print("Final answer:", event.data.generated_answer)
```

### JavaScript
```javascript
// 1) Initiate a streaming RAG request
const resultStream = await client.retrieval.rag({
  query: "What is DeepSeek R1?",
  searchSettings: { limit: 25 },
  ragGenerationConfig: { stream: true },
});

// 2) Check if we got an async iterator (streaming)
if (Symbol.asyncIterator in resultStream) {
  // 2a) Loop over each event from the server
  for await (const event of resultStream) {
    switch (event.event) {
      case "search_results":
        console.log("Search results:", event.data);
        break;
      case "message":
        console.log("Partial message delta:", event.data.delta);
        break;
      case "citation":
        console.log("New citation event:", event.data);
        break;
      case "final_answer":
        console.log("Final answer:", event.data.generated_answer);
        break;
      default:
        console.log("Unknown or unhandled event:", event);
    }
  }
} else {
  // 2b) If streaming was NOT enabled or server didn't send SSE,
  //     we'd get a single response object instead.
  console.log("Non-streaming RAG response:", resultStream);
}
```

Example output:
```plaintext
Search results: id='run_1' object='rag.search_results' data={'chunk_search_results': [...]}
Partial message: {'content': [MessageDelta(type='text', text={'value': 'Deep', 'annotations': []})]}
Partial message: {'content': [MessageDelta(type='text', text={'value': 'Seek', 'annotations': []})]}
New Citation Detected: 'cit_3a35e39'
Final answer: DeepSeek-R1 is a large language model developed by the DeepSeek-AI research team...
```

## Streaming Agentic RAG

R2R offers a powerful `agentic` retrieval mode that performs in-depth analysis of documents through iterative research and reasoning. This mode can leverage a variety of tools to thoroughly investigate your data and the web:

### Python
```python
from r2r import (
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    CitationEvent,
    FinalAnswerEvent,
    MessageEvent,
    R2RClient,
)

results = client.retrieval.agent(
    message={"role": "user", "content": "What does deepseek r1 imply for the future of AI?"},
    rag_generation_config={
        "model": "anthropic/claude-3-7-sonnet-20250219",
        "extended_thinking": True,
        "thinking_budget": 4096,
        "temperature": 1,
        "top_p": None,
        "max_tokens_to_sample": 16000,
        "stream": True
    },
)

# Process the streaming events
for event in results:
    if isinstance(event, ThinkingEvent):
        print(f"🧠 Thinking: {event.data.delta.content[0].payload.value}")
    elif isinstance(event, ToolCallEvent):
        print(f"🔧 Tool call: {event.data.name}({event.data.arguments})")
    elif isinstance(event, ToolResultEvent):
        print(f"📊 Tool result: {event.data.content[:60]}...")
    elif isinstance(event, CitationEvent):
        print(f"📑 Citation: {event.data}")
    elif isinstance(event, MessageEvent):
        print(f"💬 Message: {event.data.delta.content[0].payload.value}")
    elif isinstance(event, FinalAnswerEvent):
        print(f"✅ Final answer: {event.data.generated_answer[:100]}...")
        print(f"   Citations: {len(event.data.citations)} sources referenced")
```

### JavaScript
```javascript
const resultStream = await client.retrieval.agent({
  message: {role: "user", content: "What does deepseek r1 imply for the future of AI?"},
  generationConfig: { stream: true }
});

// Process the streaming events
if (Symbol.asyncIterator in resultStream) {
  for await (const event of resultStream) {
    switch(event.event) {
      case "thinking":
        console.log(`🧠 Thinking: ${event.data.delta.content[0].payload.value}`);
        break;
      case "tool_call":
        console.log(`🔧 Tool call: ${event.data.name}(${JSON.stringify(event.data.arguments)})`);
        break;
      case "tool_result":
        console.log(`📊 Tool result: ${event.data.content.substring(0, 60)}...`);
        break;
      case "citation":
        console.log(`📑 Citation event: ${event.data}`);
        break;
      case "message":
        console.log(`💬 Message: ${event.data.delta.content[0].payload.value}`);
        break;
      case "final_answer":
        console.log(`✅ Final answer: ${event.data.generated_answer.substring(0, 100)}...`);
        console.log(`   Citations: ${event.data.citations.length} sources referenced`);
        break;
    }
  }
}
```

Example of streaming output:
```plaintext
🧠 Thinking: Analyzing the query about DeepSeek R1 implications...
🔧 Tool call: search_file_knowledge({"query":"DeepSeek R1 capabilities advancements"})
📊 Tool result: DeepSeek-R1 is a reasoning-focused LLM that uses reinforcement learning...
🧠 Thinking: The search provides valuable information about DeepSeek R1's capabilities
🔧 Tool call: web_search({"query":"AI reasoning capabilities future development"})
📊 Tool result: Advanced reasoning capabilities are considered a key milestone toward...
💬 Message: DeepSeek-R1 has several important implications for the future of AI development:
💬 Message: 1. **Reinforcement Learning as a Key Approach**: DeepSeek-R1's success demonstrates...
✅ Final answer: DeepSeek-R1 has several important implications for the future of AI development...
   Citations: 3 sources referenced
```

## Additional Features

R2R offers additional features to enhance your document management and user experience.

### Knowledge Graphs
R2R provides powerful entity and relationship extraction capabilities that enhance document understanding and retrieval. These can be leveraged to construct knowledge graphs inside R2R. The system can automatically identify entities, build relationships between them, and create enriched knowledge graphs from your document collection.

Learn more: [Knowledge Graphs](../documentation/general/graphs.md)

### Users and Collections
R2R provides a complete set of user authentication and management features, allowing you to implement secure and feature-rich authentication systems or integrate with your preferred authentication provider. Collections enable efficient access control and organization of users and documents.

Learn more:
- [User Authentication](../documentation/general/users.md)
- [Collections](../documentation/general/collections.md)

## Next Steps

Now that you have a basic understanding of R2R's core features, you can explore more advanced topics:

- Dive into [document ingestion](../documentation/general/documents.md) and [the document API reference](../api/documents.md)
- Learn about [search and RAG](../documentation/retrieval/search-and-rag.md) and the [retrieval API reference](../api/retrieval/retrieval.md)
- Try advanced techniques like [knowledge graphs](../documentation/general/graphs.md) and refer to the [graph API reference](../api/graphs/graphs.md)
- Learn about [user authentication](../documentation/general/users.md) and [the users API reference](../api/users.md)
- Organize your documents using [collections](../api/collections.md) for granular access control
