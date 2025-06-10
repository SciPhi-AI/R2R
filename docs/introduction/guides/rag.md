# More about RAG

**On this page**
1. [Before you begin](#before-you-begin)
2. [What is RAG?](#what-is-rag)
3. [Set up RAG with R2R](#set-up-rag-with-r2r)
4. [Configure RAG settings](#configure-rag-settings)
5. [How RAG works in R2R](#how-rag-works-in-r2r)
6. [Best Practices](#best-practices)

RAG (Retrieval-Augmented Generation) combines the power of large language models with precise information retrieval from your own documents. When users ask questions, RAG first retrieves relevant information from your document collection, then uses this context to generate accurate, contextual responses. This ensures AI responses are both relevant and grounded in your specific knowledge base.

## Before you begin

RAG in R2R has the following requirements:
- A running R2R instance (local or deployed)
- Access to an LLM provider (OpenAI, Anthropic, or local models)
- Documents ingested into your R2R system
- Basic configuration for document processing and embedding generation

## What is RAG?

RAG operates in three main steps:
1. **Retrieval**: Finding relevant information from your documents
2. **Augmentation**: Adding this information as context for the AI
3. **Generation**: Creating responses using both the context and the AI's knowledge

Benefits over traditional LLM applications:
- More accurate responses based on your specific documents
- Reduced hallucination by grounding answers in real content
- Ability to work with proprietary or recent information
- Better control over AI outputs

## Set up RAG with R2R

To start using RAG in R2R:

1. Install and start R2R:
```bash
pip install r2r
r2r serve --docker
```

2. Ingest your documents:
```bash
r2r documents create --file-paths /path/to/your/documents
```

3. Test basic RAG functionality:
```bash
r2r retrieval rag --query="your question here"
```

## Configure RAG settings

R2R offers several ways to customize RAG behavior:

### Retrieval Settings

```python
# Using hybrid search (combines semantic and keyword search)
client.retrieval.rag(
    query="your question",
    vector_search_settings={"use_hybrid_search": True}
)

# Adjusting number of retrieved chunks
client.retrieval.rag(
    query="your question",
    vector_search_settings={"limit": 30}
)
```

### Generation Settings

```python
# Adjusting response style
client.retrieval.rag(
    query="your question",
    rag_generation_config={
        "temperature": 0.7,
        "model": "openai/gpt-4"
    }
)
```

## How RAG works in R2R

R2R's RAG implementation uses a sophisticated process:

### Document Processing
- Documents are split into semantic chunks
- Each chunk is embedded using AI models
- Chunks are stored with metadata and relationships

### Retrieval Process
- Queries are processed using hybrid search
- Both semantic similarity and keyword matching are considered
- Results are ranked by relevance scores

### Response Generation
- Retrieved chunks are formatted as context
- The LLM generates responses using this context
- Citations and references can be included

### Advanced Features
- GraphRAG for relationship-aware responses
- Multi-step RAG for complex queries
- Agent-based RAG for interactive conversations

## Best Practices

### Document Processing
- Use appropriate chunk sizes (256-1024 tokens)
- Maintain document metadata
- Consider document relationships

### Query Optimization
- Use hybrid search for better retrieval
- Adjust relevance thresholds
- Monitor and analyze search performance

### Response Generation
- Balance temperature for creativity vs accuracy
- Use system prompts for consistent formatting
- Implement error handling and fallbacks

## Learn More

For more detailed information, explore these resources:
- [RAG Configuration Guide](../../self-hosting/configuration/retrieval/rag.md) - Advanced configuration options
- [Search and RAG Documentation](../../documentation/retrieval/search-and-rag.md) - Complete search capabilities
- [Quickstart Guide](../../documentation/getting-started/quickstart.md) - Get started with R2R
- [System Architecture](../system.md) - Understand how RAG fits into R2R
