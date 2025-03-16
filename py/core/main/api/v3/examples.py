import textwrap

"""
This file contains updated OpenAPI examples for the RetrievalRouterV3 class.
These examples are designed to be included in the openapi_extra field for each route.
"""

# Updated examples for search_app endpoint
search_app_examples = {
    "x-codeSamples": [
        {
            "lang": "Python",
            "source": textwrap.dedent(
                """
                from r2r import R2RClient

                client = R2RClient()
                # if using auth, do client.login(...)

                # Basic search
                response = client.retrieval.search(
                    query="What is DeepSeek R1?",
                )

                # Advanced mode with specific filters
                response = client.retrieval.search(
                    query="What is DeepSeek R1?",
                    search_mode="advanced",
                    search_settings={
                        "filters": {"document_id": {"$eq": "e43864f5-a36f-548e-aacd-6f8d48b30c7f"}},
                        "limit": 5
                    }
                )

                # Using hybrid search
                response = client.retrieval.search(
                    query="What was Uber's profit in 2020?",
                    search_settings={
                        "use_hybrid_search": True,
                        "hybrid_settings": {
                            "full_text_weight": 1.0,
                            "semantic_weight": 5.0,
                            "full_text_limit": 200,
                            "rrf_k": 50
                        },
                        "filters": {"title": {"$in": ["DeepSeek_R1.pdf"]}},
                    }
                )

                # Advanced filtering
                results = client.retrieval.search(
                    query="What are the effects of climate change?",
                    search_settings={
                        "filters": {
                            "$and":[
                                {"document_type": {"$eq": "pdf"}},
                                {"metadata.year": {"$gt": 2020}}
                            ]
                        },
                        "limit": 10
                    }
                )

                # Knowledge graph enhanced search
                results = client.retrieval.search(
                    query="What was DeepSeek R1",
                    graph_search_settings={
                        "use_graph_search": True,
                        "kg_search_type": "local"
                    }
                )
                """
            ),
        },
        {
            "lang": "JavaScript",
            "source": textwrap.dedent(
                """
                const { r2rClient } = require("r2r-js");

                const client = new r2rClient();
                // if using auth, do client.login(...)

                // Basic search
                const response = await client.retrieval.search({
                    query: "What is DeepSeek R1?",
                });

                // With specific filters
                const filteredResponse = await client.retrieval.search({
                    query: "What is DeepSeek R1?",
                    searchSettings: {
                        filters: {"document_id": {"$eq": "e43864f5-a36f-548e-aacd-6f8d48b30c7f"}},
                        limit: 5
                    }
                });

                // Using hybrid search
                const hybridResponse = await client.retrieval.search({
                    query: "What was Uber's profit in 2020?",
                    searchSettings: {
                        indexMeasure: "l2_distance",
                        useHybridSearch: true,
                        hybridSettings: {
                            fullTextWeight: 1.0,
                            semanticWeight: 5.0,
                            fullTextLimit: 200,
                        },
                        filters: {"title": {"$in": ["DeepSeek_R1.pdf"]}},
                    }
                });

                // Advanced filtering
                const advancedResults = await client.retrieval.search({
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

                // Knowledge graph enhanced search
                const kgResults = await client.retrieval.search({
                    query: "who was aristotle?",
                    graphSearchSettings: {
                        useKgSearch: true,
                        kgSearchType: "local"
                    }
                });
                """
            ),
        },
        {
            "lang": "Shell",
            "source": textwrap.dedent(
                """
                # Basic search
                curl -X POST "https://api.sciphi.ai/v3/retrieval/search" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
                    -d '{
                    "query": "What is DeepSeek R1?"
                }'

                # With hybrid search and filters
                curl -X POST "https://api.sciphi.ai/v3/retrieval/search" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
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
                        "filters": {"title": {"$in": ["DeepSeek_R1.pdf"]}},
                        "limit": 10,
                        "chunk_settings": {
                        "index_measure": "l2_distance",
                        "probes": 25,
                        "ef_search": 100
                        }
                    }
                    }'

                # Knowledge graph enhanced search
                curl -X POST "https://api.sciphi.ai/v3/retrieval/search" \\
                    -H "Content-Type: application/json" \\
                    -d '{
                        "query": "who was aristotle?",
                        "graph_search_settings": {
                        "use_graph_search": true,
                        "kg_search_type": "local"
                        }
                    }' \\
                    -H "Authorization: Bearer YOUR_API_KEY"
                """
            ),
        },
    ]
}

# Updated examples for rag_app endpoint
rag_app_examples = {
    "x-codeSamples": [
        {
            "lang": "Python",
            "source": textwrap.dedent(
                """
                from r2r import R2RClient

                client = R2RClient()
                # when using auth, do client.login(...)

                # Basic RAG request
                response = client.retrieval.rag(
                    query="What is DeepSeek R1?",
                )

                # Advanced RAG with custom search settings
                response = client.retrieval.rag(
                    query="What is DeepSeek R1?",
                    search_settings={
                        "use_semantic_search": True,
                        "filters": {"document_id": {"$eq": "e43864f5-a36f-548e-aacd-6f8d48b30c7f"}},
                        "limit": 10,
                    },
                    rag_generation_config={
                        "stream": False,
                        "temperature": 0.7,
                        "max_tokens": 1500
                    }
                )

                # Hybrid search in RAG
                results = client.retrieval.rag(
                    "Who is Jon Snow?",
                    search_settings={"use_hybrid_search": True}
                )

                # Custom model selection
                response = client.retrieval.rag(
                    "Who was Aristotle?",
                    rag_generation_config={"model":"anthropic/claude-3-haiku-20240307", "stream": True}
                )
                for chunk in response:
                    print(chunk)

                # Streaming RAG
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

                # Process different event types
                for event in result_stream:
                    if isinstance(event, SearchResultsEvent):
                        print("Search results:", event.data)
                    elif isinstance(event, MessageEvent):
                        print("Partial message:", event.data.delta)
                    elif isinstance(event, CitationEvent):
                        print("New citation detected:", event.data.id)
                    elif isinstance(event, FinalAnswerEvent):
                        print("Final answer:", event.data.generated_answer)
                """
            ),
        },
        {
            "lang": "JavaScript",
            "source": textwrap.dedent(
                """
                const { r2rClient } = require("r2r-js");

                const client = new r2rClient();
                // when using auth, do client.login(...)

                // Basic RAG request
                const response = await client.retrieval.rag({
                    query: "What is DeepSeek R1?",
                });

                // RAG with custom settings
                const advancedResponse = await client.retrieval.rag({
                    query: "What is DeepSeek R1?",
                    searchSettings: {
                        useSemanticSearch: true,
                        filters: {"document_id": {"$eq": "e43864f5-a36f-548e-aacd-6f8d48b30c7f"}},
                        limit: 10,
                    },
                    ragGenerationConfig: {
                        stream: false,
                        temperature: 0.7,
                        maxTokens: 1500
                    }
                });

                // Hybrid search in RAG
                const hybridResults = await client.retrieval.rag({
                    query: "Who is Jon Snow?",
                    searchSettings: {
                        useHybridSearch: true
                    },
                });

                // Custom model
                const customModelResponse = await client.retrieval.rag({
                    query: "Who was Aristotle?",
                    ragGenerationConfig: {
                        model: 'anthropic/claude-3-haiku-20240307',
                        temperature: 0.7,
                    }
                });

                // Streaming RAG
                const resultStream = await client.retrieval.rag({
                    query: "What is DeepSeek R1?",
                    searchSettings: { limit: 25 },
                    ragGenerationConfig: { stream: true },
                });

                // Process streaming events
                if (Symbol.asyncIterator in resultStream) {
                    for await (const event of resultStream) {
                        switch (event.event) {
                            case "search_results":
                                console.log("Search results:", event.data);
                                break;
                            case "message":
                                console.log("Partial message delta:", event.data.delta);
                                break;
                            case "citation":
                                console.log("New citation event:", event.data.id);
                                break;
                            case "final_answer":
                                console.log("Final answer:", event.data.generated_answer);
                                break;
                            default:
                                console.log("Unknown or unhandled event:", event);
                        }
                    }
                }
                """
            ),
        },
        {
            "lang": "Shell",
            "source": textwrap.dedent(
                """
                # Basic RAG request
                curl -X POST "https://api.sciphi.ai/v3/retrieval/rag" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
                    -d '{
                    "query": "What is DeepSeek R1?"
                }'

                # RAG with custom settings
                curl -X POST "https://api.sciphi.ai/v3/retrieval/rag" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
                    -d '{
                    "query": "What is DeepSeek R1?",
                    "search_settings": {
                        "use_semantic_search": true,
                        "filters": {"document_id": {"$eq": "e43864f5-a36f-548e-aacd-6f8d48b30c7f"}},
                        "limit": 10
                    },
                    "rag_generation_config": {
                        "stream": false,
                        "temperature": 0.7,
                        "max_tokens": 1500
                    }
                }'

                # Hybrid search in RAG
                curl -X POST "https://api.sciphi.ai/v3/retrieval/rag" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
                    -d '{
                    "query": "Who is Jon Snow?",
                    "search_settings": {
                        "use_hybrid_search": true,
                        "filters": {},
                        "limit": 10
                    }
                }'

                # Custom model
                curl -X POST "https://api.sciphi.ai/v3/retrieval/rag" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
                    -d '{
                    "query": "Who is Jon Snow?",
                    "rag_generation_config": {
                        "model": "anthropic/claude-3-haiku-20240307",
                        "temperature": 0.7
                    }
                }'
                """
            ),
        },
    ]
}

# Updated examples for agent_app endpoint
agent_app_examples = {
    "x-codeSamples": [
        {
            "lang": "Python",
            "source": textwrap.dedent(
                """
from r2r import R2RClient
from r2r import (
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    CitationEvent,
    FinalAnswerEvent,
    MessageEvent,
)

client = R2RClient()
# when using auth, do client.login(...)

# Basic synchronous request
response = client.retrieval.agent(
    message={
        "role": "user",
        "content": "Do a deep analysis of the philosophical implications of DeepSeek R1"
    },
    rag_tools=["web_search", "web_scrape", "search_file_descriptions", "search_file_knowledge", "get_file_content"],
)

# Advanced analysis with streaming and extended thinking
streaming_response = client.retrieval.agent(
    message={
        "role": "user",
        "content": "Do a deep analysis of the philosophical implications of DeepSeek R1"
    },
    search_settings={"limit": 20},
    rag_tools=["web_search", "web_scrape", "search_file_descriptions", "search_file_knowledge", "get_file_content"],
    rag_generation_config={
        "model": "anthropic/claude-3-7-sonnet-20250219",
        "extended_thinking": True,
        "thinking_budget": 4096,
        "temperature": 1,
        "top_p": None,
        "max_tokens": 16000,
        "stream": True
    }
)

# Process streaming events with emoji only on type change
current_event_type = None
for event in streaming_response:
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
        print(f"{event.data.id}")
    elif isinstance(event, MessageEvent):
        print(f"{event.data.delta.content[0].payload.value}", end="", flush=True)
    elif isinstance(event, FinalAnswerEvent):
        print(f"{event.data.generated_answer[:100]}...")
        print(f"   Citations: {len(event.data.citations)} sources referenced")

# Conversation with multiple turns (synchronous)
conversation = client.conversations.create()

# First message in conversation
results_1 = client.retrieval.agent(
    query="What does DeepSeek R1 imply for the future of AI?",
    rag_generation_config={
        "model": "anthropic/claude-3-7-sonnet-20250219",
        "extended_thinking": True,
        "thinking_budget": 4096,
        "temperature": 1,
        "top_p": None,
        "max_tokens": 16000,
        "stream": True
    },
    conversation_id=conversation.results.id
)

# Follow-up query in the same conversation
results_2 = client.retrieval.agent(
    query="How does it compare to other reasoning models?",
    rag_generation_config={
        "model": "anthropic/claude-3-7-sonnet-20250219",
        "extended_thinking": True,
        "thinking_budget": 4096,
        "temperature": 1,
        "top_p": None,
        "max_tokens": 16000,
        "stream": True
    },
    conversation_id=conversation.results.id
)

# Access the final results
print(f"First response: {results_1.generated_answer[:100]}...")
print(f"Follow-up response: {results_2.generated_answer[:100]}...")
"""
            ),
        },
        {
            "lang": "JavaScript",
            "source": textwrap.dedent(
                """
                const { r2rClient } = require("r2r-js");

                const client = new r2rClient();
                // when using auth, do client.login(...)

                async function main() {
                    // Basic synchronous request
                    const ragResponse = await client.retrieval.agent({
                        message: {
                            role: "user",
                            content: "Do a deep analysis of the philosophical implications of DeepSeek R1"
                        },
                        ragTools: ["web_search", "web_scrape", "search_file_descriptions", "search_file_knowledge", "get_file_content"]
                    });

                    // Advanced analysis with streaming and extended thinking
                    const streamingResponse = await client.retrieval.agent({
                        message: {
                            role: "user",
                            content: "Do a deep analysis of the philosophical implications of DeepSeek R1"
                        },
                        searchSettings: {limit: 20},
                        ragTools: ["web_search", "web_scrape", "search_file_descriptions", "search_file_knowledge", "get_file_content"],
                        ragGenerationConfig: {
                            model: "anthropic/claude-3-7-sonnet-20250219",
                            extendedThinking: true,
                            thinkingBudget: 4096,
                            temperature: 1,
                            maxTokens: 16000,
                            stream: true
                        }
                    });

                    // Process streaming events with emoji only on type change
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
                                    console.log(`${event.data.id}`);
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

                    // Conversation with multiple turns (synchronous)
                    const conversation = await client.conversations.create();

                    // First message in conversation
                    const results1 = await client.retrieval.agent({
                        query: "What does DeepSeek R1 imply for the future of AI?",
                        ragGenerationConfig: {
                            model: "anthropic/claude-3-7-sonnet-20250219",
                            extendedThinking: true,
                            thinkingBudget: 4096,
                            temperature: 1,
                            maxTokens: 16000,
                            stream: true
                        },
                        conversationId: conversation.results.id
                    });

                    // Follow-up query in the same conversation
                    const results2 = await client.retrieval.agent({
                        query: "How does it compare to other reasoning models?",
                        ragGenerationConfig: {
                            model: "anthropic/claude-3-7-sonnet-20250219",
                            extendedThinking: true,
                            thinkingBudget: 4096,
                            temperature: 1,
                            maxTokens: 16000,
                            stream: true
                        },
                        conversationId: conversation.results.id
                    });

                    // Log the results
                    console.log(`First response: ${results1.generated_answer.substring(0, 100)}...`);
                    console.log(`Follow-up response: ${results2.generated_answer.substring(0, 100)}...`);
                }

                main();
                """
            ),
        },
        {
            "lang": "Shell",
            "source": textwrap.dedent(
                """
                # Basic request
                curl -X POST "https://api.sciphi.ai/v3/retrieval/agent" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
                    -d '{
                    "message": {
                        "role": "user",
                        "content": "What were the key contributions of Aristotle to logic?"
                    },
                    "search_settings": {
                        "use_semantic_search": true,
                        "filters": {"document_id": {"$eq": "e43864f5-a36f-548e-aacd-6f8d48b30c7f"}}
                    },
                    "rag_tools": ["search_file_knowledge", "content", "web_search"]
                }'

                # Advanced analysis with extended thinking
                curl -X POST "https://api.sciphi.ai/v3/retrieval/agent" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
                    -d '{
                    "message": {
                        "role": "user",
                        "content": "Do a deep analysis of the philosophical implications of DeepSeek R1"
                    },
                    "search_settings": {"limit": 20},
                    "research_tools": ["rag", "reasoning", "critique", "python_executor"],
                    "rag_generation_config": {
                        "model": "anthropic/claude-3-7-sonnet-20250219",
                        "extended_thinking": true,
                        "thinking_budget": 4096,
                        "temperature": 1,
                        "top_p": null,
                        "max_tokens": 16000,
                        "stream": true
                    }
                }'

                # Conversation continuation
                curl -X POST "https://api.sciphi.ai/v3/retrieval/agent" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
                    -d '{
                    "message": {
                        "role": "user",
                        "content": "How does it compare to other reasoning models?"
                    },
                    "conversation_id": "YOUR_CONVERSATION_ID"
                }'
                """
            ),
        },
    ]
}

# Updated examples for completion endpoint
completion_examples = {
    "x-codeSamples": [
        {
            "lang": "Python",
            "source": textwrap.dedent(
                """
                from r2r import R2RClient

                client = R2RClient()
                # when using auth, do client.login(...)

                response = client.completion(
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "What is the capital of France?"},
                        {"role": "assistant", "content": "The capital of France is Paris."},
                        {"role": "user", "content": "What about Italy?"}
                    ],
                    generation_config={
                        "model": "openai/gpt-4o-mini",
                        "temperature": 0.7,
                        "max_tokens": 150,
                        "stream": False
                    }
                )
                """
            ),
        },
        {
            "lang": "JavaScript",
            "source": textwrap.dedent(
                """
                const { r2rClient } = require("r2r-js");

                const client = new r2rClient();
                // when using auth, do client.login(...)

                async function main() {
                    const response = await client.completion({
                        messages: [
                            { role: "system", content: "You are a helpful assistant." },
                            { role: "user", content: "What is the capital of France?" },
                            { role: "assistant", content: "The capital of France is Paris." },
                            { role: "user", content: "What about Italy?" }
                        ],
                        generationConfig: {
                            model: "openai/gpt-4o-mini",
                            temperature: 0.7,
                            maxTokens: 150,
                            stream: false
                        }
                    });
                }

                main();
                """
            ),
        },
        {
            "lang": "Shell",
            "source": textwrap.dedent(
                """
                curl -X POST "https://api.sciphi.ai/v3/retrieval/completion" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
                    -d '{
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "What is the capital of France?"},
                        {"role": "assistant", "content": "The capital of France is Paris."},
                        {"role": "user", "content": "What about Italy?"}
                    ],
                    "generation_config": {
                        "model": "openai/gpt-4o-mini",
                        "temperature": 0.7,
                        "max_tokens": 150,
                        "stream": false
                    }
                    }'
                """
            ),
        },
    ]
}

# Updated examples for embedding endpoint
embedding_examples = {
    "x-codeSamples": [
        {
            "lang": "Python",
            "source": textwrap.dedent(
                """
                from r2r import R2RClient

                client = R2RClient()
                # when using auth, do client.login(...)

                result = client.retrieval.embedding(
                    text="What is DeepSeek R1?",
                )
                """
            ),
        },
        {
            "lang": "JavaScript",
            "source": textwrap.dedent(
                """
                const { r2rClient } = require("r2r-js");

                const client = new r2rClient();
                // when using auth, do client.login(...)

                async function main() {
                    const response = await client.retrieval.embedding({
                        text: "What is DeepSeek R1?",
                    });
                }

                main();
                """
            ),
        },
        {
            "lang": "Shell",
            "source": textwrap.dedent(
                """
                curl -X POST "https://api.sciphi.ai/v3/retrieval/embedding" \\
                    -H "Content-Type: application/json" \\
                    -H "Authorization: Bearer YOUR_API_KEY" \\
                    -d '{
                    "text": "What is DeepSeek R1?",
                    }'
                """
            ),
        },
    ]
}

# Updated rag_app docstring
rag_app_docstring = """
Execute a RAG (Retrieval-Augmented Generation) query.

This endpoint combines search results with language model generation to produce accurate,
contextually-relevant responses based on your document corpus.

**Features:**
- Combines vector search, optional knowledge graph integration, and LLM generation
- Automatically cites sources with unique citation identifiers
- Supports both streaming and non-streaming responses
- Compatible with various LLM providers (OpenAI, Anthropic, etc.)
- Web search integration for up-to-date information

**Search Configuration:**
All search parameters from the search endpoint apply here, including filters, hybrid search, and graph-enhanced search.

**Generation Configuration:**
Fine-tune the language model's behavior with `rag_generation_config`:
```json
{
  "model": "openai/gpt-4o-mini",  // Model to use
  "temperature": 0.7,              // Control randomness (0-1)
  "max_tokens": 1500,              // Maximum output length
  "stream": true                   // Enable token streaming
}
```

**Model Support:**
- OpenAI models (default)
- Anthropic Claude models (requires ANTHROPIC_API_KEY)
- Local models via Ollama
- Any provider supported by LiteLLM

**Streaming Responses:**
When `stream: true` is set, the endpoint returns Server-Sent Events with the following types:
- `search_results`: Initial search results from your documents
- `message`: Partial tokens as they're generated
- `citation`: Citation metadata when sources are referenced
- `final_answer`: Complete answer with structured citations

**Example Response:**
```json
{
  "generated_answer": "DeepSeek-R1 is a model that demonstrates impressive performance...[1]",
  "search_results": { ... },
  "citations": [
    {
      "id": "cit.123456",
      "object": "citation",
      "payload": { ... }
    }
  ]
}
```
"""

# Updated agent_app docstring
agent_app_docstring = """
Engage with an intelligent agent for information retrieval, analysis, and research.

This endpoint offers two operating modes:
- **RAG mode**: Standard retrieval-augmented generation for answering questions based on knowledge base
- **Research mode**: Advanced capabilities for deep analysis, reasoning, and computation

### RAG Mode (Default)

The RAG mode provides fast, knowledge-based responses using:
- Semantic and hybrid search capabilities
- Document-level and chunk-level content retrieval
- Optional web search integration
- Source citation and evidence-based responses

### Research Mode

The Research mode builds on RAG capabilities and adds:
- A dedicated reasoning system for complex problem-solving
- Critique capabilities to identify potential biases or logical fallacies
- Python execution for computational analysis
- Multi-step reasoning for deeper exploration of topics

### Available Tools

**RAG Tools:**
- `search_file_knowledge`: Semantic/hybrid search on your ingested documents
- `search_file_descriptions`: Search over file-level metadata
- `content`: Fetch entire documents or chunk structures
- `web_search`: Query external search APIs for up-to-date information
- `web_scrape`: Scrape and extract content from specific web pages

**Research Tools:**
- `rag`: Leverage the underlying RAG agent for information retrieval
- `reasoning`: Call a dedicated model for complex analytical thinking
- `critique`: Analyze conversation history to identify flaws and biases
- `python_executor`: Execute Python code for complex calculations and analysis

### Streaming Output

When streaming is enabled, the agent produces different event types:
- `thinking`: Shows the model's step-by-step reasoning (when extended_thinking=true)
- `tool_call`: Shows when the agent invokes a tool
- `tool_result`: Shows the result of a tool call
- `citation`: Indicates when a citation is added to the response
- `message`: Streams partial tokens of the response
- `final_answer`: Contains the complete generated answer and structured citations

### Conversations

Maintain context across multiple turns by including `conversation_id` in each request.
After your first call, store the returned `conversation_id` and include it in subsequent calls.
"""

# Updated completion_docstring
completion_docstring = """
Generate completions for a list of messages.

This endpoint uses the language model to generate completions for the provided messages.
The generation process can be customized using the generation_config parameter.

The messages list should contain alternating user and assistant messages, with an optional
system message at the start. Each message should have a 'role' and 'content'.

**Generation Configuration:**
Fine-tune the language model's behavior with `generation_config`:
```json
{
  "model": "openai/gpt-4o-mini",  // Model to use
  "temperature": 0.7,              // Control randomness (0-1)
  "max_tokens": 1500,              // Maximum output length
  "stream": true                   // Enable token streaming
}
```

**Multiple LLM Support:**
- OpenAI models (default)
- Anthropic Claude models (requires ANTHROPIC_API_KEY)
- Local models via Ollama
- Any provider supported by LiteLLM
"""

# Updated embedding_docstring
embedding_docstring = """
Generate embeddings for the provided text using the specified model.

This endpoint uses the language model to generate embeddings for the provided text.
The model parameter specifies the model to use for generating embeddings.

Embeddings are numerical representations of text that capture semantic meaning,
allowing for similarity comparisons and other vector operations.

**Uses:**
- Semantic search
- Document clustering
- Text similarity analysis
- Content recommendation
"""

# # Example implementation to update the routers in the RetrievalRouterV3 class
# def update_retrieval_router(router_class):
#     """
#     Update the RetrievalRouterV3 class with the improved docstrings and examples.

#     This function demonstrates how the updated examples and docstrings would be
#     integrated into the actual router class.
#     """
#     # Update search_app endpoint
#     router_class.search_app.__doc__ = search_app_docstring
#     router_class.search_app.openapi_extra = search_app_examples

#     # Update rag_app endpoint
#     router_class.rag_app.__doc__ = rag_app_docstring
#     router_class.rag_app.openapi_extra = rag_app_examples

#     # Update agent_app endpoint
#     router_class.agent_app.__doc__ = agent_app_docstring
#     router_class.agent_app.openapi_extra = agent_app_examples

#     # Update completion endpoint
#     router_class.completion.__doc__ = completion_docstring
#     router_class.completion.openapi_extra = completion_examples

#     # Update embedding endpoint
#     router_class.embedding.__doc__ = embedding_docstring
#     router_class.embedding.openapi_extra = embedding_examples

#     return router_class

# Example showing how the updated router would be integrated
"""
from your_module import RetrievalRouterV3

# Apply the updated docstrings and examples
router = RetrievalRouterV3(providers, services, config)
router = update_retrieval_router(router)

# Now the router has the improved docstrings and examples
"""

EXAMPLES = {
    "search": search_app_examples,
    "rag": rag_app_examples,
    "agent": agent_app_examples,
    "completion": completion_examples,
    "embedding": embedding_examples,
}
