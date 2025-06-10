R2R provides powerful search and retrieval capabilities through vector search, full-text search, hybrid search, and Retrieval-Augmented Generation (RAG). The system supports multiple search modes and extensive runtime configuration to help you find and contextualize information effectively.

Refer to the retrieval API and SDK reference for detailed retrieval examples.

## Search Modes and Settings

When using the Search (`/retrieval/search`) or RAG (`/retrieval/rag`) endpoints, you control the retrieval process using `search_mode` and `search_settings`.

*   **`search_mode`** (Optional, defaults to `custom`): Choose between pre-configured modes or full customization.
    *   `basic`: Defaults to a simple semantic search configuration. Good for quick setup.
    *   `advanced`: Defaults to a hybrid search configuration combining semantic and full-text. Offers broader results.
    *   `custom`: Allows full control via the `search_settings` object. If `search_settings` are omitted in `custom` mode, default vector search settings are applied.
*   **`search_settings`** (Optional): A detailed configuration object. If provided alongside `basic` or `advanced` modes, these settings will override the mode's defaults. Key settings include:
    *   `use_semantic_search`: Boolean to enable/disable vector-based semantic search (default: `true` unless overridden).
    *   `use_fulltext_search`: Boolean to enable/disable keyword-based full-text search (default: `false` unless using hybrid).
    *   `use_hybrid_search`: Boolean to enable hybrid search, combining semantic and full-text (default: `false`). Requires `hybrid_settings`.
    *   `filters`: Apply complex filtering rules using MongoDB-like syntax (see "Advanced Filtering" below).
    *   `limit`: Integer controlling the maximum number of results to return (default: `10`).
    *   `hybrid_settings`: Object to configure weights (`semantic_weight`, `full_text_weight`), limits (`full_text_limit`), and fusion (`rrf_k`) for hybrid search.
    *   `chunk_settings`: Object to fine-tune vector index parameters like `index_measure` (distance metric), `probes`, `ef_search`.
    *   `search_strategy`: String to enable advanced RAG techniques like `"hyde"` or `"rag_fusion"` (default: `"vanilla"`). See [Advanced RAG](/documentation/advanced-rag).
    *   `include_scores`: Boolean to include relevance scores in the results (default: `true`).
    *   `include_metadatas`: Boolean to include metadata in the results (default: `true`).

## AI Powered Search (`/retrieval/search`)

R2R offers powerful and highly configurable search capabilities. This endpoint returns raw search results without LLM generation.

### Basic Search Example

This performs a search using default configurations or a specified mode.

<Tabs>
<Tab title="Python">
```python
# Uses default settings (likely semantic search in 'custom' mode)
results = client.retrieval.search(
  query="What is DeepSeek R1?",
)

# Explicitly using 'basic' mode
results_basic = client.retrieval.search(
  query="What is DeepSeek R1?",
  search_mode="basic",
)
```
</Tab>
<Tab title="JavaScript">
```javascript
// Uses default settings
const results = await client.retrieval.search({
  query: "What is DeepSeek R1?",
});

// Explicitly using 'basic' mode
const resultsBasic = await client.retrieval.search({
  query: "What is DeepSeek R1?",
  searchMode: "basic",
});
```
</Tab>

<Tab title="Curl">
```bash
# Uses default settings
curl -X POST "https://api.sciphi.ai/v3/retrieval/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "query": "What is DeepSeek R1?"
  }'

# Explicitly using 'basic' mode
curl -X POST "https://api.sciphi.ai/v3/retrieval/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "query": "What is DeepSeek R1?",
    "search_mode": "basic"
  }'
```
</Tab>
</Tabs>

**Response Structure (`WrappedSearchResponse`):**

The search endpoint returns a `WrappedSearchResponse` containing an `AggregateSearchResult` object with fields like:
*   `results.chunk_search_results`: A list of relevant text `ChunkSearchResult` objects found (containing `id`, `document_id`, `text`, `score`, `metadata`).
*   `results.graph_search_results`: A list of relevant `GraphSearchResult` objects (entities, relationships, communities) if graph search is active and finds results.
*   `results.web_search_results`: A list of `WebSearchResult` objects (if web search was somehow enabled, though typically done via RAG/Agent).

```json
// Simplified Example Structure
{
  "results": {
    "chunk_search_results": [
      {
        "score": 0.643,
        "text": "Document Title: DeepSeek_R1.pdf...",
        "id": "chunk-uuid-...",
        "document_id": "doc-uuid-...",
        "metadata": { ... }
      },
      // ... more chunks
    ],
    "graph_search_results": [
      // Example: An entity result if graph search ran
      {
         "id": "graph-entity-uuid...",
         "content": { "name": "DeepSeek-R1", "description": "A large language model...", "id": "entity-uuid..." },
         "result_type": "ENTITY",
         "score": 0.95,
         "metadata": { ... }
      }
      // ... potentially relationships or communities
    ],
    "web_search_results": []
  }
}
```

### Hybrid Search Example

Combine keyword-based (full-text) search with vector search for potentially broader results.

<Tabs>

<Tab title="Python">
```python
hybrid_results = client.retrieval.search(
    query="What was Uber's profit in 2020?",
    search_settings={
        "use_hybrid_search": True,
        "hybrid_settings": {
            "full_text_weight": 1.0,
            "semantic_weight": 5.0,
            "full_text_limit": 200, # How many full-text results to initially consider
            "rrf_k": 50, # Parameter for Reciprocal Rank Fusion
        },
        "filters": {"metadata.title": {"$in": ["uber_2021.pdf"]}}, # Filter by metadata field
        "limit": 10 # Final number of results after fusion/ranking
    },
)
```
</Tab>

<Tab title="JavaScript">
```javascript
const hybridResults = await client.retrieval.search({
  query: "What was Uber's profit in 2020?",
  searchSettings: {
    useHybridSearch: true,
    hybridSettings: {
        fullTextWeight: 1.0,
        semanticWeight: 5.0,
        fullTextLimit: 200,
        rrfK: 50 // Assuming camelCase mapping in JS SDK
    },
    filters: {"metadata.title": {"$in": ["uber_2021.pdf"]}},
    limit: 10
  },
});
```
</Tab>

<Tab title="Curl">
```bash
curl -X POST "https://api.sciphi.ai/v3/retrieval/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "query": "What was Uber'\''s profit in 2020?",
    "search_settings": {
      "use_hybrid_search": true,
      "hybrid_settings": {
        "full_text_weight": 1.0,
        "semantic_weight": 5.0,
        "full_text_limit": 200,
        "rrf_k": 50
      },
      "filters": {"metadata.title": {"$in": ["uber_2021.pdf"]}},
      "limit": 10,
      "chunk_settings": {
        "index_measure": "l2_distance"
      }
    }
  }'
```
</Tab>
</Tabs>

### Advanced Filtering

Apply filters to narrow search results based on document properties or metadata. Supported operators include `$eq`, `$neq`, `$gt`, `$gte`, `$lt`, `$lte`, `$like`, `$ilike`, `$in`, `$nin`. You can combine filters using `$and` and `$or`.

<Tabs>
<Tab title="Python">
```python
filtered_results = client.retrieval.search(
    query="What are the effects of climate change?",
    search_settings={
        "filters": {
            "$and":[
                {"document_type": {"$eq": "pdf"}}, # Assuming 'document_type' is stored
                {"metadata.year": {"$gt": 2020}} # Access nested metadata fields
            ]
        },
        "limit": 10
    }
)
```
</Tab>

<Tab title="JavaScript">
```javascript
const filteredResults = await client.retrieval.search({
  query: "What are the effects of climate change?",
  searchSettings: {
    filters: {
      $and: [
        {document_type: {$eq: "pdf"}},
        {"metadata.year": {$gt: 2020}}
      ]
    },
    limit: 10
  }
});
```
</Tab>
</Tabs>

### Distance Measures for Vector Search
Distance metrics for vector search, which can be configured through the `chunk_settings.index_measure` parameter. Choosing the right distance measure can significantly impact search quality depending on your embeddings and use case:

* **`cosine_distance`** (Default): Measures the cosine of the angle between vectors, ignoring magnitude. Best for comparing documents regardless of their length.
* **`l2_distance`** (Euclidean): Measures the straight-line distance between vectors. Useful when both direction and magnitude matter.
* **`max_inner_product`**: Optimized for finding vectors with similar direction. Good for recommendation systems.
* **`l1_distance`** (Manhattan): Measures the sum of absolute differences. Less sensitive to outliers than L2.
* **`hamming_distance`**: Counts the positions at which vectors differ. Best for binary embeddings.
* **`jaccard_distance`**: Measures dissimilarity between sample sets. Useful for sparse embeddings.

<Tabs>
  <Tab title="Python">
    ```python
    results = client.retrieval.search(
      query="What are the key features of quantum computing?",
      search_settings={
        "chunk_settings": {
          "index_measure": "l2_distance"  # Use Euclidean distance instead of default
        }
      }
    )
    ```
  </Tab>
</Tabs>
For most text embedding models (e.g., OpenAI's models), cosine_distance is recommended. For specialized embeddings or specific use cases, experiment with different measures to find the optimal setting for your data.


## Knowledge Graph Enhanced Retrieval

Beyond searching through text chunks, R2R can leverage knowledge graphs to enrich the retrieval process. This offers several benefits:

*   **Contextual Understanding:** Knowledge graphs store information as entities (like people, organizations, concepts) and relationships (like "works for", "is related to", "is a type of"). Searching the graph allows R2R to find connections and context that might be missed by purely text-based search.
*   **Relationship-Based Queries:** Answer questions that rely on understanding connections, such as "What projects is Person X involved in?" or "How does Concept A relate to Concept B?".
*   **Discovering Structure:** Graph search can reveal higher-level structures, such as communities of related entities or key connecting concepts within your data.
*   **Complementary Results:** Graph results (entities, relationships, community summaries) complement text chunks by providing structured information and broader context.

When knowledge graph search is active within R2R, the `AggregateSearchResult` returned by the Search or RAG endpoints may include relevant items in the `graph_search_results` list, enhancing the context available for understanding or generation.

## Retrieval-Augmented Generation (RAG) (`/retrieval/rag`)

R2R's RAG engine combines the search capabilities above (including text, vector, hybrid, and potentially graph results) with Large Language Models (LLMs) to generate contextually relevant responses grounded in your ingested documents and optional web search results.

### RAG Configuration (`rag_generation_config`)

Control the LLM's generation process:
*   `model`: Specify the LLM to use (e.g., `"openai/gpt-4o-mini"`, `"anthropic/claude-3-haiku-20240307"`). Defaults are set in R2R config.
*   `stream`: Boolean (default `false`). Set to `true` for streaming responses.
*   `temperature`, `max_tokens`, `top_p`, etc.: Standard LLM generation parameters.

### Basic RAG

Generate a response using retrieved context. Uses the same `search_mode` and `search_settings` as the search endpoint to find relevant information.

<Tabs>
<Tab title="Python">
```python
# Basic RAG call using default search and generation settings
rag_response = client.retrieval.rag(query="What is DeepSeek R1?")
```
</Tab>

<Tab title="JavaScript">
```javascript
// Basic RAG call using default settings
const ragResponse = await client.retrieval.rag({ query: "What is DeepSeek R1?" });
```
</Tab>

<Tab title="Curl">
```bash
curl -X POST "https://api.sciphi.ai/v3/retrieval/rag" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "query": "What is DeepSeek R1?"
  }'
```
</Tab>
</Tabs>

**Response Structure (`WrappedRAGResponse`):**

The non-streaming RAG endpoint returns a `WrappedRAGResponse` containing an `RAGResponse` object with fields like:
*   `results.generated_answer`: The final synthesized answer from the LLM.
*   `results.search_results`: The `AggregateSearchResult` used to generate the answer (containing chunks, possibly graph results, and web results).
*   `results.citations`: A list of `Citation` objects linking parts of the answer to specific sources (`ChunkSearchResult`, `GraphSearchResult`, `WebSearchResult`, etc.) found in `search_results`. Each citation includes an `id` (short identifier used in the text like `[1]`) and a `payload` containing the source object.
*   `results.metadata`: LLM provider metadata about the generation call.

```json
// Simplified Example Structure
{
  "results": {
    "generated_answer": "DeepSeek-R1 is a model that... [1]. It excels in tasks... [2].",
    "search_results": {
      "chunk_search_results": [ { "id": "chunk-abc...", "text": "...", "score": 0.8 }, /* ... */ ],
      "graph_search_results": [ { /* Graph Entity/Relationship */ } ],
      "web_search_results": [ { "url": "...", "title": "...", "snippet": "..." }, /* ... */ ]
    },
    "citations": [
      {
        "id": "cit.1", // Corresponds to [1] in text
        "object": "citation",
        "payload": { /* ChunkSearchResult for chunk-abc... */ }
      },
      {
        "id": "cit.2", // Corresponds to [2] in text
        "object": "citation",
        "payload": { /* WebSearchResult for relevant web page */ }
      }
      // ... more citations potentially linking to graph results too
    ],
    "metadata": { "model": "openai/gpt-4o-mini", ... }
  }
}

```

### RAG with Web Search Integration

Enhance RAG responses with up-to-date information from the web by setting `include_web_search=True`.

<Tabs>
<Tab title="Python">
```python
web_rag_response = client.retrieval.rag(
    query="What are the latest developments with DeepSeek R1?",
    include_web_search=True
)
```
</Tab>

<Tab title="JavaScript">
```javascript
const webRagResponse = await client.retrieval.rag({
  query: "What are the latest developments with DeepSeek R1?",
  includeWebSearch: true // Use camelCase for JS SDK
});
```
</Tab>

<Tab title="Curl">
```bash
curl -X POST "https://api.sciphi.ai/v3/retrieval/rag" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "query": "What are the latest developments with DeepSeek R1?",
    "include_web_search": true
  }'
```
</Tab>
</Tabs>

When enabled, R2R performs a web search using the query, and the results are added to the context provided to the LLM alongside results from your documents or knowledge graph.

### RAG with Hybrid Search

Combine hybrid search with RAG by configuring `search_settings`.

<Tabs>
<Tab title="Python">
```python
hybrid_rag_response = client.retrieval.rag(
    query="Who is Jon Snow?",
    search_settings={"use_hybrid_search": True}
)
```
</Tab>

<Tab title="JavaScript">
```javascript
const hybridRagResponse = await client.retrieval.rag({
  query: "Who is Jon Snow?",
  searchSettings: {
    useHybridSearch: true
  },
});
```
</Tab>

<Tab title="Curl">
```bash
# Correctly place use_hybrid_search in search_settings
curl -X POST "https://api.sciphi.ai/v3/retrieval/rag" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "query": "Who is Jon Snow?",
    "search_settings": {
      "use_hybrid_search": true,
      "limit": 10
    }
  }'
```
</Tab>
</Tabs>

### Streaming RAG

Receive RAG responses as a stream of Server-Sent Events (SSE) by setting `stream: True` in `rag_generation_config`. This is ideal for real-time applications.

**Event Types:**

1.  `search_results`: Contains the initial `AggregateSearchResult` (sent once at the beginning).
    *   `data`: The full `AggregateSearchResult` object (chunks, potentially graph results, web results).
2.  `message`: Streams partial tokens of the response as they are generated.
    *   `data.delta.content`: The text chunk being streamed.
3.  `citation`: Indicates when a citation source is identified. Sent *once* per unique source when it's first referenced.
    *   `data.id`: The short citation ID (e.g., `"cit.1"`).
    *   `data.payload`: The full source object (`ChunkSearchResult`, `GraphSearchResult`, `WebSearchResult`, etc.).
    *   `data.is_new`: True if this is the first time this citation ID is sent.
    *   `data.span`: The start/end character indices in the *current* accumulated text where the citation marker (e.g., `[1]`) appears.
4.  `final_answer`: Sent once at the end, containing the complete generated answer and structured citations.
    *   `data.generated_answer`: The full final text.
    *   `data.citations`: List of all citations, including their `id`, `payload`, and all `spans` where they appeared in the final text.

<Tabs>
<Tab title="Python">
```python
from r2r import (
    CitationEvent,
    FinalAnswerEvent,
    MessageEvent,
    SearchResultsEvent,
    R2RClient,
    # Assuming ThinkingEvent is imported if needed, though not standard in basic RAG
)

# Set stream=True in rag_generation_config
result_stream = client.retrieval.rag(
    query="What is DeepSeek R1?",
    search_settings={"limit": 25},
    rag_generation_config={"stream": True, "model": "openai/gpt-4o-mini"},
    include_web_search=True,
)

for event in result_stream:
    if isinstance(event, SearchResultsEvent):
        print(f"Search results received (Chunks: {len(event.data.data.chunk_search_results)}, Graph: {len(event.data.data.graph_search_results)}, Web: {len(event.data.data.web_search_results)})")
    elif isinstance(event, MessageEvent):
        # Access the actual text delta
        if event.data.delta and event.data.delta.content and event.data.delta.content[0].type == 'text' and event.data.delta.content[0].payload.value:
             print(event.data.delta.content[0].payload.value, end="", flush=True)
    elif isinstance(event, CitationEvent):
        # Payload is only sent when is_new is True
        if event.data.is_new:
            print(f"\n<<< New Citation Source Detected: ID={event.data.id} >>>")

    elif isinstance(event, FinalAnswerEvent):
        print("\n\n--- Final Answer ---")
        print(event.data.generated_answer)
        print("\n--- Citations Summary ---")
        for cit in event.data.citations:
             print(f"  ID: {cit.id}, Spans: {cit.span}")
```
</Tab>

<Tab title="JavaScript">
```javascript
// Set stream: true in ragGenerationConfig
const resultStream = await client.retrieval.rag({
  query: "What is DeepSeek R1?",
  searchSettings: { limit: 25 },
  ragGenerationConfig: { stream: true, model: "openai/gpt-4o-mini" },
  includeWebSearch: true,
});

// Check if we got an async iterator (streaming)
if (Symbol.asyncIterator in resultStream) {
  console.log("Starting stream processing...");
  // Loop over each event from the server
  for await (const event of resultStream) {
      switch (event.event) {
      case "search_results":
          console.log(`\nSearch results received (Chunks: ${event.data.chunk_search_results?.length || 0}, Graph: ${event.data.graph_search_results?.length || 0}, Web: ${event.data.web_search_results?.length || 0})`);
          break;
      case "message":
          // Access the actual text delta
          if (event.data?.delta?.content?.[0]?.text?.value) {
            process.stdout.write(event.data.delta.content[0].text.value);
          }
          break;
      case "citation":
          // Payload only sent when is_new is true
          if (event.data?.is_new) {
            process.stdout.write(`\n<<< New Citation Source Detected: ID=${event.data.id} >>>`);
            // console.log(`   Payload: ${JSON.stringify(event.data.payload)}`); // Can be verbose
          } else {
             // Citation already seen, no need to log payload again
          }
          break;
      case "final_answer":
          process.stdout.write("\n\n--- Final Answer ---\n");
          console.log(event.data.generated_answer);
          console.log("\n--- Citations Summary ---");
          event.data.citations?.forEach(cit => {
            console.log(`  ID: ${cit.id}, Spans: ${JSON.stringify(cit.spans)}`);
            // console.log(`  Payload: ${JSON.stringify(cit.payload)}`); // Can be verbose
          });
          break;
      default:
          console.log("\nUnknown or unhandled event:", event.event);
      }
  }
  console.log("\nStream finished.");
} else {
  // Handle non-streaming response if necessary (though we requested stream)
  console.log("Received non-streaming response:", resultStream);
}
```
</Tab>
</Tabs>

### Customizing RAG

Besides `search_settings`, you can customize RAG generation using `rag_generation_config`.

Example of customizing the model with web search:

<Tabs>
<Tab title="Python">
```python
# Requires ANTHROPIC_API_KEY env var if using Anthropic models
response = client.retrieval.rag(
  query="Who was Aristotle and what are his recent influences?",
  rag_generation_config={
      "model":"anthropic/claude-3-haiku-20240307",
      "stream": False, # Get a single response object
      "temperature": 0.5
  },
  include_web_search=True
)
print(response.results.generated_answer)
```
</Tab>

<Tab title="JavaScript">
```javascript
// Requires ANTHROPIC_API_KEY env var if using Anthropic models
const response = await client.retrieval.rag({
  query: "Who was Aristotle and what are his recent influences?",
  ragGenerationConfig: {
    model: 'anthropic/claude-3-haiku-20240307',
    temperature: 0.5,
    stream: false // Get a single response object
  },
  includeWebSearch: true
});
console.log(response.results.generated_answer);
```
</Tab>

<Tab title="Curl">
```bash
# Requires ANTHROPIC_API_KEY env var if using Anthropic models
curl -X POST "https://api.sciphi.ai/v3/retrieval/rag" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -d '{
        "query": "Who was Aristotle and what are his recent influences?",
        "rag_generation_config": {
            "model": "anthropic/claude-3-haiku-20240307",
            "temperature": 0.5,
            "stream": false
        },
        "include_web_search": true
    }'
```
</Tab>
</Tabs>

## Conclusion

R2R's search and RAG capabilities provide flexible tools for finding and contextualizing information. Whether you need simple semantic search, advanced hybrid retrieval with filtering, or customizable RAG generation incorporating document chunks, knowledge graph insights, and web results via streaming or single responses, the system can be configured to meet your specific needs.
