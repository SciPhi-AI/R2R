import { r2rClient } from "../../r2rClient";

import {
  GenerationConfig,
  Message,
  SearchSettings,
  WrappedSearchResponse,
} from "../../types";
import { ensureSnakeCase } from "../../utils";

function parseSseEvent(raw: { event: string; data: string }) {
  // Some SSE servers send a "done" event at the end:
  if (raw.event === "done") return null;

  try {
    const parsedJson = JSON.parse(raw.data);
    return {
      event: raw.event,
      data: parsedJson,
    };
  } catch (err) {
    console.error("Failed to parse SSE line:", raw.data, err);
    return null;
  }
}

export class RetrievalClient {
  constructor(private client: r2rClient) {}

  /**
   * Perform a search query on the vector database and knowledge graph and
   * any other configured search engines.
   *
   * This endpoint allows for complex filtering of search results using
   * PostgreSQL-based queries. Filters can be applied to various fields
   * such as document_id, and internal metadata values.
   *
   * Allowed operators include: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`,
   * `like`, `ilike`, `in`, and `nin`.
   * @param query Search query to find relevant documents
   * @param searchSettings Settings for the search
   * @returns
   */
  async search(options: {
    query: string;
    searchMode?: "advanced" | "basic" | "custom";
    searchSettings?: SearchSettings | Record<string, any>;
  }): Promise<WrappedSearchResponse> {
    const data = {
      query: options.query,
      ...(options.searchSettings && {
        search_settings: ensureSnakeCase(options.searchSettings),
      }),
      ...(options.searchMode && {
        search_mode: options.searchMode,
      }),
    };

    return await this.client.makeRequest("POST", "retrieval/search", {
      data: data,
    });
  }

  /**
   * Execute a RAG (Retrieval-Augmented Generation) query.
   *
   * This endpoint combines search results with language model generation.
   * It supports the same filtering capabilities as the search endpoint,
   * allowing for precise control over the retrieved context.
   *
   * The generation process can be customized using the `rag_generation_config` parameter.
   * @param query
   * @param searchSettings Settings for the search
   * @param ragGenerationConfig Configuration for RAG generation
   * @param taskPrompt Optional custom prompt to override default
   * @param includeTitleIfAvailable Include document titles in responses when available
   * @returns
   */
  async rag(options: {
    query: string;
    searchMode?: "advanced" | "basic" | "custom";
    searchSettings?: SearchSettings | Record<string, any>;
    ragGenerationConfig?: GenerationConfig | Record<string, any>;
    taskPrompt?: string;
    includeTitleIfAvailable?: boolean;
    includeWebSearch?: boolean;
  }): Promise<any | ReadableStream<Uint8Array>> {
    const data = {
      query: options.query,
      ...(options.searchMode && {
        search_mode: options.searchMode,
      }),
      ...(options.searchSettings && {
        search_settings: ensureSnakeCase(options.searchSettings),
      }),
      ...(options.ragGenerationConfig && {
        rag_generation_config: ensureSnakeCase(options.ragGenerationConfig),
      }),
      ...(options.taskPrompt && {
        task_prompt_override: options.taskPrompt,
      }),
      ...(options.includeTitleIfAvailable !== undefined && {
        include_title_if_available: options.includeTitleIfAvailable,
      }),
      ...(options.includeWebSearch && {
        include_web_search: options.includeWebSearch,
      }),
    };

    if (options.ragGenerationConfig && options.ragGenerationConfig.stream) {
      return this.streamRag(data);
    } else {
      return await this.client.makeRequest("POST", "retrieval/rag", {
        data: data,
      });
    }
  }

  private async streamRag(
    ragData: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    return this.client.makeRequest<ReadableStream<Uint8Array>>(
      "POST",
      "retrieval/rag",
      {
        data: ragData,
        headers: { "Content-Type": "application/json" },
        responseType: "stream",
      },
    );
  }

  /**
   * Engage with an intelligent RAG-powered conversational agent for complex
   * information retrieval and analysis.
   *
   * This advanced endpoint combines retrieval-augmented generation (RAG)
   * with a conversational AI agent to provide detailed, context-aware
   * responses based on your document collection.
   *
   * The agent can:
   *    - Maintain conversation context across multiple interactions
   *    - Dynamically search and retrieve relevant information from both
   *      vector and knowledge graph sources
   *    - Break down complex queries into sub-questions for comprehensive
   *      answers
   *    - Cite sources and provide evidence-based responses
   *    - Handle follow-up questions and clarifications
   *    - Navigate complex topics with multi-step reasoning
   *
   * This endpoint offers two operating modes:
   *    - RAG mode: Standard retrieval-augmented generation for answering questions
   *      based on knowledge base
   *    - Research mode: Advanced capabilities for deep analysis, reasoning, and computation
   *
   * @param message Current message to process
   * @param ragGenerationConfig Configuration for RAG generation in 'rag' mode
   * @param researchGenerationConfig Configuration for generation in 'research' mode
   * @param searchMode Search mode to use, either "basic", "advanced", or "custom"
   * @param searchSettings Settings for the search
   * @param taskPrompt Optional custom prompt to override default
   * @param includeTitleIfAvailable Include document titles in responses when available
   * @param conversationId ID of the conversation
   * @param tools List of tool configurations (deprecated)
   * @param ragTools List of tools to enable for RAG mode
   * @param researchTools List of tools to enable for Research mode
   * @param maxToolContextLength Maximum context length for tool replies
   * @param useSystemContext Use system context for generation
   * @param mode Mode to use, either "rag" or "research"
   * @param needsInitialConversationName Whether the conversation needs an initial name
   * @returns
   */
  async agent(options: {
    message: Message;
    ragGenerationConfig?: GenerationConfig | Record<string, any>;
    researchGenerationConfig?: GenerationConfig | Record<string, any>;
    searchMode?: "basic" | "advanced" | "custom";
    searchSettings?: SearchSettings | Record<string, any>;
    taskPrompt?: string;
    includeTitleIfAvailable?: boolean;
    conversationId?: string;
    maxToolContextLength?: number;
    tools?: Array<string>; // Deprecated
    ragTools?: Array<string>;
    researchTools?: Array<string>;
    useSystemContext?: boolean;
    mode?: "rag" | "research";
    needsInitialConversationName?: boolean;
  }): Promise<any | ReadableStream<Uint8Array>> {
    const data: Record<string, any> = {
      message: options.message,
      ...(options.searchMode && {
        search_mode: options.searchMode,
      }),
      ...(options.ragGenerationConfig && {
        rag_generation_config: ensureSnakeCase(options.ragGenerationConfig),
      }),
      ...(options.researchGenerationConfig && {
        research_generation_config: ensureSnakeCase(
          options.researchGenerationConfig,
        ),
      }),
      ...(options.searchSettings && {
        search_settings: ensureSnakeCase(options.searchSettings),
      }),
      ...(options.taskPrompt && {
        task_prompt: options.taskPrompt,
      }),
      ...(typeof options.includeTitleIfAvailable && {
        include_title_if_available: options.includeTitleIfAvailable,
      }),
      ...(options.conversationId && {
        conversation_id: options.conversationId,
      }),
      ...(options.maxToolContextLength && {
        max_tool_context_length: options.maxToolContextLength,
      }),
      ...(options.tools && {
        tools: options.tools,
      }),
      ...(options.ragTools && {
        rag_tools: options.ragTools,
      }),
      ...(options.researchTools && {
        research_tools: options.researchTools,
      }),
      ...(typeof options.useSystemContext !== undefined && {
        use_system_context: options.useSystemContext,
      }),
      ...(options.mode && {
        mode: options.mode,
      }),
      ...(options.needsInitialConversationName && {
        needsInitialConversationName: options.needsInitialConversationName,
      }),
    };

    // Determine if streaming is enabled
    let isStream = false;
    if (options.ragGenerationConfig && options.ragGenerationConfig.stream) {
      isStream = true;
    } else if (
      options.researchGenerationConfig &&
      options.mode === "research" &&
      options.researchGenerationConfig.stream
    ) {
      isStream = true;
    }

    if (isStream) {
      return this.streamAgent(data);
    } else {
      return await this.client.makeRequest("POST", "retrieval/agent", {
        data: data,
      });
    }
  }

  private async streamAgent(
    agentData: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    // Return the raw stream like streamCompletion does
    return this.client.makeRequest<ReadableStream<Uint8Array>>(
      "POST",
      "retrieval/agent",
      {
        data: agentData,
        headers: { "Content-Type": "application/json" },
        responseType: "stream",
      },
    );
  }

  /**
   * Generate completions for a list of messages.
   *
   * This endpoint uses the language model to generate completions for
   * the provided messages. The generation process can be customized using
   * the generation_config parameter.
   *
   * The messages list should contain alternating user and assistant
   * messages, with an optional system message at the start. Each message
   * should have a 'role' and 'content'.
   * @param messages List of messages to generate completion for
   * @returns
   */
  async completion(options: {
    messages: Message[];
    generationConfig?: GenerationConfig | Record<string, any>;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
    const data = {
      messages: options.messages,
      ...(options.generationConfig && {
        generation_config: options.generationConfig,
      }),
    };

    if (options.generationConfig && options.generationConfig.stream) {
      return this.streamCompletion(data);
    } else {
      return await this.client.makeRequest("POST", "retrieval/completion", {
        data: data,
      });
    }
  }

  private async streamCompletion(
    ragData: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    return this.client.makeRequest<ReadableStream<Uint8Array>>(
      "POST",
      "retrieval/completion",
      {
        data: ragData,
        headers: {
          "Content-Type": "application/json",
        },
        responseType: "stream",
      },
    );
  }
  /**
   * Engage with an intelligent reasoning agent for complex information analysis.
   *
   * This endpoint provides a streamlined version of the agent that focuses on
   * reasoning capabilities without RAG integration. It's ideal for scenarios
   * where you need complex reasoning but don't require document retrieval.
   *
   * Key Features:
   *    - Multi-step reasoning for complex problems
   *    - Tool integration for enhanced capabilities
   *    - Conversation context management
   *    - Streaming support for real-time responses
   *
   * @param options Configuration options for the reasoning agent
   * @param options.message Current message to process
   * @param options.ragGenerationConfig Configuration for generation
   * @param options.conversationId ID of the conversation
   * @param options.maxToolContextLength Maximum context length for tool replies
   * @param options.tools List of tool configurations
   * @returns
   */
  async reasoningAgent(options: {
    message?: Message;
    ragGenerationConfig?: GenerationConfig | Record<string, any>;
    conversationId?: string;
    maxToolContextLength?: number;
    tools?: Array<Record<string, any>>;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
    const data: Record<string, any> = {
      ...(options.message && {
        message: options.message,
      }),
      ...(options.ragGenerationConfig && {
        rag_generation_config: ensureSnakeCase(options.ragGenerationConfig),
      }),
      ...(options.conversationId && {
        conversation_id: options.conversationId,
      }),
      ...(options.maxToolContextLength && {
        max_tool_context_length: options.maxToolContextLength,
      }),
      ...(options.tools && {
        tools: options.tools,
      }),
    };

    if (options.ragGenerationConfig && options.ragGenerationConfig.stream) {
      return this.streamReasoningAgent(data);
    } else {
      return await this.client.makeRequest(
        "POST",
        "retrieval/reasoning_agent",
        {
          data: data,
        },
      );
    }
  }

  private async streamReasoningAgent(
    agentData: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    return this.client.makeRequest<ReadableStream<Uint8Array>>(
      "POST",
      "retrieval/reasoning_agent",
      {
        data: agentData,
        headers: {
          "Content-Type": "application/json",
        },
        responseType: "stream",
      },
    );
  }
  /**
   * Generate embeddings for the provided text.
   *
   * This endpoint generates vector embeddings that can be used for
   * semantic similarity comparisons or other vector operations.
   *
   * @param text Text to generate embeddings for
   * @returns Vector embedding of the input text
   */
  async embedding(text: string): Promise<number[]> {
    return await this.client.makeRequest("POST", "retrieval/embedding", {
      data: { text },
    });
  }
}
