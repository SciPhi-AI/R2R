## Introduction
R2R's **Agentic RAG** orchestrates multi-step reasoning with Retrieval-Augmented Generation (RAG). By pairing large language models with advanced retrieval and tool integrations, the agent can fetch relevant data from the internet, your documents and knowledge graphs, reason over it, and produce robust, context-aware answers.

<Note>
Agentic RAG (also called Deep Research) is an extension of R2R's basic retrieval functionality. If you are new to R2R, we suggest starting with the [Quickstart](/documentation/quickstart) and [Search & RAG](/documentation/search-and-rag) docs first.
</Note>

## Key Features

<CardGroup cols={2}>
  <Card title="Multi-Step Reasoning" icon="diagram-project">
    The agent can chain multiple actions, like searching documents or referencing conversation history, before generating its final response.
  </Card>
  <Card title="Retrieval Augmentation" icon="binoculars">
    Integrates with R2R's vector, full-text, or hybrid search to gather the most relevant context for each query.
  </Card>
</CardGroup>

<CardGroup cols={2}>
  <Card title="Conversation Context" icon="comment">
    Maintain dialogue across multiple turns by including <code>conversation_id</code> in each request.
  </Card>
  <Card title="Tool Usage" icon="wrench">
    Dynamically invoke tools at runtime to gather and analyze information from various sources.
  </Card>
</CardGroup>

## Available Modes

The Agentic RAG system offers two primary operating modes:

### RAG Mode (Default)

Standard retrieval-augmented generation for answering questions based on your knowledge base:
- Semantic and hybrid search capabilities
- Document-level and chunk-level content retrieval
- Optional web search integrations, leveraging Serper and Firecrawl
- Source citation and evidence-based responses

### Research Mode

Advanced capabilities for deep analysis, reasoning, and computation:
- All RAG mode capabilities
- A dedicated reasoning system for complex problem-solving
- Critique capabilities to identify potential biases or logical fallacies
- Python execution for computational analysis
- Multi-step reasoning for deeper exploration of topics

## Available Tools

### RAG Tools

The agent can use the following tools in RAG mode:

| Tool Name | Description | Dependencies |
|-----------|-------------|-------------|
| `search_file_knowledge` | Semantic/hybrid search on your ingested documents using R2R's search capabilities | None |
| `search_file_descriptions` | Search over file-level metadata (titles, doc-level descriptions) | None |
| `get_file_content` | Fetch entire documents or chunk structures for deeper analysis | None |
| `web_search` | Query external search APIs for up-to-date information | Requires `SERPER_API_KEY` environment variable ([serper.dev](https://serper.dev/)) |
| `web_scrape` | Scrape and extract content from specific web pages | Requires `FIRECRAWL_API_KEY` environment variable ([firecrawl.dev](https://www.firecrawl.dev/)) |

### Research Tools

The agent can use the following tools in Research mode:

| Tool Name | Description | Dependencies |
|-----------|-------------|-------------|
| `rag` | Leverage the underlying RAG agent to perform information retrieval and synthesis | None |
| `reasoning` | Call a dedicated model for complex analytical thinking | None |
| `critique` | Analyze conversation history to identify flaws, biases, and alternative approaches | None |
| `python_executor` | Execute Python code for complex calculations and analysis | None |

## Basic Usage

Below are examples of how to use the agent for both single-turn queries and multi-turn conversations.


```python
from r2r import R2RClient
from r2r import (
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    CitationEvent,
    MessageEvent,
    FinalAnswerEvent,
)

# when using auth, do client.users.login(...)

# Basic RAG mode with streaming
response = client.retrieval.agent(
    message={
        "role": "user",
        "content": "What does DeepSeek R1 imply for the future of AI?"
    },
    rag_generation_config={
        "model": "anthropic/claude-3-7-sonnet-20250219",
        "extended_thinking": True,
        "thinking_budget": 4096,
        "temperature": 1,
        "top_p": None,
        "max_tokens_to_sample": 16000,
        "stream": True
    },
    rag_tools=["search_file_knowledge", "get_file_content"],
    mode="rag"
)

# Improved streaming event handling
current_event_type = None
for event in response:
    # Check if the event type has changed
    event_type = type(event)
    if event_type != current_event_type:
        current_event_type = event_type
        print() # Add newline before new event type

        # Print emoji based on the new event type
        if isinstance(event, ThinkingEvent):
            print(f"\n🧠 Thinking: ", end="", flush=True)
        elif isinstance(event, ToolCallEvent):
            print(f"\n🔧 Tool call: ", end="", flush=True)
        elif isinstance(event, ToolResultEvent):
            print(f"\n📊 Tool result: ", end="", flush=True)
        elif isinstance(event, CitationEvent):
            print(f"\n📑 Citation: ", end="", flush=True)
        elif isinstance(event, MessageEvent):
            print(f"\n💬 Message: ", end="", flush=True)
        elif isinstance(event, FinalAnswerEvent):
            print(f"\n✅ Final answer: ", end="", flush=True)

    # Print the content without the emoji
    if isinstance(event, ThinkingEvent):
        print(f"{event.data.delta.content[0].payload.value}", end="", flush=True)
    elif isinstance(event, ToolCallEvent):
        print(f"{event.data.name}({event.data.arguments})")
    elif isinstance(event, ToolResultEvent):
        print(f"{event.data.content[:60]}...")
    elif isinstance(event, CitationEvent):
        print(f"{event.data}")
    elif isinstance(event, MessageEvent):
        print(f"{event.data.delta.content[0].payload.value}", end="", flush=True)
    elif isinstance(event, FinalAnswerEvent):
        print(f"{event.data.generated_answer[:100]}...")
        print(f"   Citations: {len(event.data.citations)} sources referenced")
```

```javascript
const { r2rClient } = require("r2r-js");

const client = new r2rClient();
// when using auth, do client.users.login(...)

async function main() {
    // Basic RAG mode with streaming
    const streamingResponse = await client.retrieval.agent({
        message: {
            role: "user",
            content: "What does DeepSeek R1 imply for the future of AI?"
        },
        ragTools: ["search_file_knowledge", "get_file_content"],
        ragGenerationConfig: {
            model: "anthropic/claude-3-7-sonnet-20250219",
            extendedThinking: true,
            thinkingBudget: 4096,
            temperature: 1,
            maxTokens: 16000,
            stream: true
        }
    });

    // Improved streaming event handling
    if (Symbol.asyncIterator in streamingResponse) {
        let currentEventType = null;

        for await (const event of streamingResponse) {
            // Check if event type has changed
            const eventType = event.event;
            if (eventType !== currentEventType) {
                currentEventType = eventType;
                console.log(); // Add newline before new event type

                // Print emoji based on the new event type
                switch(eventType) {
                    case "thinking":
                        process.stdout.write(`🧠 Thinking: `);
                        break;
                    case "tool_call":
                        process.stdout.write(`🔧 Tool call: `);
                        break;
                    case "tool_result":
                        process.stdout.write(`📊 Tool result: `);
                        break;
                    case "citation":
                        process.stdout.write(`📑 Citation: `);
                        break;
                    case "message":
                        process.stdout.write(`💬 Message: `);
                        break;
                    case "final_answer":
                        process.stdout.write(`✅ Final answer: `);
                        break;
                }
            }

            // Print content based on event type
            switch(eventType) {
                case "thinking":
                    process.stdout.write(`${event.data.delta.content[0].payload.value}`);
                    break;
                case "tool_call":
                    console.log(`${event.data.name}(${JSON.stringify(event.data.arguments)})`);
                    break;
                case "tool_result":
                    console.log(`${event.data.content.substring(0, 60)}...`);
                    break;
                case "citation":
                    console.log(`${event.data}`);
                    break;
                case "message":
                    process.stdout.write(`${event.data.delta.content[0].payload.value}`);
                    break;
                case "final_answer":
                    console.log(`${event.data.generated_answer.substring(0, 100)}...`);
                    console.log(`   Citations: ${event.data.citations.length} sources referenced`);
                    break;
            }
        }
    }
}

main();
```

```bash
curl -X POST "https://api.sciphi.ai/v3/retrieval/agent" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "message": {
        "role": "user",
        "content": "What does DeepSeek R1 imply for the future of AI?"
    },
    "rag_tools": ["search_file_knowledge", "get_file_content"],
    "rag_generation_config": {
        "model": "anthropic/claude-3-7-sonnet-20250219",
        "extended_thinking": true,
        "thinking_budget": 4096,
        "temperature": 1,
        "max_tokens_to_sample": 16000,
        "stream": true
    },
    "mode": "rag"
  }'
```

## Using Research Mode

Research mode provides more advanced reasoning capabilities for complex questions:

```python
# Research mode with all available tools
response = client.retrieval.agent(
    message={
        "role": "user",
        "content": "Analyze the philosophical implications of DeepSeek R1 for the future of AI reasoning"
    },
    research_generation_config={
        "model": "anthropic/claude-3-opus-20240229",
        "extended_thinking": True,
        "thinking_budget": 8192,
        "temperature": 0.2,
        "max_tokens_to_sample": 32000,
        "stream": True
    },
    research_tools=["rag", "reasoning", "critique", "python_executor"],
    mode="research"
)

# Process streaming events as shown in the previous example
# ...

# Research mode with computational focus
# This example solves a mathematical problem using the python_executor tool
compute_response = client.retrieval.agent(
    message={
        "role": "user",
        "content": "Calculate the factorial of 15 multiplied by 32. Show your work."
    },
    research_generation_config={
        "model": "anthropic/claude-3-opus-20240229",
        "max_tokens_to_sample": 1000,
        "stream": False
    },
    research_tools=["python_executor"],
    mode="research"
)

print(f"Final answer: {compute_response.results.messages[-1].content}")
```

```javascript
// Research mode with all available tools
const researchStream = await client.retrieval.agent({
    message: {
        role: "user",
        content: "Analyze the philosophical implications of DeepSeek R1 for the future of AI reasoning"
    },
    researchGenerationConfig: {
        model: "anthropic/claude-3-opus-20240229",
        extendedThinking: true,
        thinkingBudget: 8192,
        temperature: 0.2,
        maxTokens: 32000,
        stream: true
    },
    researchTools: ["rag", "reasoning", "critique", "python_executor"],
    mode: "research"
});

// Process streaming events as shown in the previous example
// ...

// Research mode with computational focus
const computeResponse = await client.retrieval.agent({
    message: {
        role: "user",
        content: "Calculate the factorial of 15 multiplied by 32. Show your work."
    },
    researchGenerationConfig: {
        model: "anthropic/claude-3-opus-20240229",
        maxTokens: 1000,
        stream: false
    },
    researchTools: ["python_executor"],
    mode: "research"
});

console.log(`Final answer: ${computeResponse.results.messages[computeResponse.results.messages.length - 1].content}`);
```

## Customizing the Agent

### Tool Selection

You can customize which tools the agent has access to:

```python
# RAG mode with web capabilities
response = client.retrieval.agent(
    message={"role": "user", "content": "What are the latest developments in AI safety?"},
    rag_tools=["search_file_knowledge", "get_file_content", "web_search", "web_scrape"],
    mode="rag"
)

# Research mode with limited tools
response = client.retrieval.agent(
    message={"role": "user", "content": "Analyze the complexity of this algorithm"},
    research_tools=["reasoning", "python_executor"],  # Only reasoning and code execution
    mode="research"
)
```

### Search Settings Propagation

Any search settings passed to the agent will propagate to downstream searches. This includes:

- Filters to restrict document sources
- Limits on the number of results
- Hybrid search configuration
- Collection restrictions

```python
# Using search settings with the agent
response = client.retrieval.agent(
    message={"role": "user", "content": "Summarize our Q1 financial results"},
    search_settings={
        "use_semantic_search": True,
        "filters": {"collection_ids": {"$overlap": ["e43864f5-..."]}},
        "limit": 25
    },
    rag_tools=["search_file_knowledge", "get_file_content"],
    mode="rag"
)
```

### Model Selection and Parameters

You can customize the agent's behavior by selecting different models and adjusting generation parameters:

```python
# Using a specific model with custom parameters
response = client.retrieval.agent(
    message={"role": "user", "content": "Write a concise summary of DeepSeek R1's capabilities"},
    rag_generation_config={
        "model": "anthropic/claude-3-haiku-20240307",  # Faster model for simpler tasks
        "temperature": 0.3,                           # Lower temperature for more deterministic output
        "max_tokens_to_sample": 500,                  # Limit response length
        "stream": False                               # Non-streaming for simpler use cases
    },
    mode="rag"
)
```

## Multi-Turn Conversations

You can maintain context across multiple turns using `conversation_id`. The agent will remember previous interactions and build upon them in subsequent responses.

```python
# Create a new conversation
conversation = client.conversations.create()
conversation_id = conversation.results.id

# First turn
first_response = client.retrieval.agent(
    message={"role": "user", "content": "What does DeepSeek R1 imply for the future of AI?"},
    rag_generation_config={
        "model": "anthropic/claude-3-7-sonnet-20250219",
        "temperature": 0.7,
        "max_tokens_to_sample": 1000,
        "stream": False
    },
    conversation_id=conversation_id,
    mode="rag"
)
print(f"First response: {first_response.results.messages[-1].content[:100]}...")

# Follow-up query in the same conversation
follow_up_response = client.retrieval.agent(
    message={"role": "user", "content": "How does it compare to other reasoning models?"},
    rag_generation_config={
        "model": "anthropic/claude-3-7-sonnet-20250219",
        "temperature": 0.7,
        "max_tokens_to_sample": 1000,
        "stream": False
    },
    conversation_id=conversation_id,
    mode="rag"
)
print(f"Follow-up response: {follow_up_response.results.messages[-1].content[:100]}...")

# The agent maintains context, so it knows "it" refers to DeepSeek R1
```

```javascript
// Create a new conversation
const conversation = await client.conversations.create();
const conversationId = conversation.results.id;

// First turn
const firstResponse = await client.retrieval.agent({
    message: {
        role: "user",
        content: "What does DeepSeek R1 imply for the future of AI?"
    },
    ragGenerationConfig: {
        model: "anthropic/claude-3-7-sonnet-20250219",
        temperature: 0.7,
        maxTokens: 1000,
        stream: false
    },
    conversationId: conversationId,
    mode: "rag"
});
console.log(`First response: ${firstResponse.results.messages[firstResponse.results.messages.length - 1].content.substring(0, 100)}...`);

// Follow-up query in the same conversation
const followUpResponse = await client.retrieval.agent({
    message: {
        role: "user",
        content: "How does it compare to other reasoning models?"
    },
    ragGenerationConfig: {
        model: "anthropic/claude-3-7-sonnet-20250219",
        temperature: 0.7,
        maxTokens: 1000,
        stream: false
    },
    conversationId: conversationId,
    mode: "rag"
});
console.log(`Follow-up response: ${followUpResponse.results.messages[followUpResponse.results.messages.length - 1].content.substring(0, 100)}...`);

// The agent maintains context, so it knows "it" refers to DeepSeek R1
```

## Performance Considerations

Based on our integration testing, here are some considerations to optimize your agent usage:

### Response Time Management

Response times vary based on the complexity of the query, the number of tools used, and the length of the requested output:

```python
# For time-sensitive applications, consider:
# 1. Using a smaller max_tokens value
# 2. Selecting faster models like claude-3-haiku
# 3. Avoiding unnecessary tools

fast_response = client.retrieval.agent(
    message={"role": "user", "content": "Give me a quick overview of DeepSeek R1"},
    rag_generation_config={
        "model": "anthropic/claude-3-haiku-20240307",  # Faster model
        "max_tokens_to_sample": 200,                   # Limited output
        "stream": True                                 # Stream for perceived responsiveness
    },
    rag_tools=["search_file_knowledge"],              # Minimal tools
    mode="rag"
)
```

### Handling Large Context

The agent can process large document contexts efficiently, but performance can be improved by using appropriate filters:

```python
# When working with large document collections, use filters to narrow results
filtered_response = client.retrieval.agent(
    message={"role": "user", "content": "Summarize key points from our AI ethics documentation"},
    search_settings={
        "filters": {
            "$and": [
                {"document_type": {"$eq": "pdf"}},
                {"metadata.category": {"$eq": "ethics"}},
                {"metadata.year": {"$gt": 2023}}
            ]
        },
        "limit": 10  # Limit number of chunks returned
    },
    rag_generation_config={
        "max_tokens_to_sample": 500,
        "stream": True
    },
    mode="rag"
)
```

## How Tools Work (Under the Hood)

R2R's Agentic RAG leverages a powerful toolset to conduct comprehensive research:

### RAG Mode Tools

- **search_file_knowledge**: Looks up relevant text chunks and knowledge graph data from your ingested documents using semantic and hybrid search capabilities.
- **search_file_descriptions**: Searches over file-level metadata (titles, doc-level descriptions) rather than chunk content.
- **get_file_content**: Fetches entire documents or their chunk structures for deeper analysis when the agent needs more comprehensive context.
- **web_search**: Queries external search APIs (like Serper or Google) for live, up-to-date information from the internet. Requires a `SERPER_API_KEY` environment variable.
- **web_scrape**: Uses Firecrawl to extract content from specific web pages for in-depth analysis. Requires a `FIRECRAWL_API_KEY` environment variable.

### Research Mode Tools

- **rag**: A specialized research tool that utilizes the underlying RAG agent to perform comprehensive information retrieval and synthesis across your data sources.
- **python_executor**: Executes Python code for complex calculations, statistical operations, and algorithmic implementations, giving the agent computational capabilities.
- **reasoning**: Allows the research agent to call a dedicated model as an external module for complex analytical thinking.
- **critique**: Analyzes conversation history to identify potential flaws, biases, and alternative approaches to improve research rigor.

The Agent is built on a sophisticated architecture that combines these tools with streaming capabilities and flexible response formats. It can decide which tools to use based on the query requirements and can dynamically invoke them during the research process.

## Conclusion

Agentic RAG provides a powerful approach to retrieval-augmented generation. By combining **advanced search**, **multi-step reasoning**, **conversation context**, and **dynamic tool usage**, the agent helps you build sophisticated Q&A or research solutions on your R2R-ingested data.
