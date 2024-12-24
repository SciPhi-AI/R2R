import { r2rClient } from "../../r2rClient";

import { Message } from "../../models";
import { feature } from "../../feature";
import {
  SearchSettings,
  WrappedSearchResponse,
  GenerationConfig,
} from "../../types";
import { ensureSnakeCase } from "../../utils";

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
  @feature("retrieval.search")
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
   * @param taskPromptOverride Optional custom prompt to override default
   * @param includeTitleIfAvailable Include document titles in responses when available
   * @returns
   */
  @feature("retrieval.rag")
  async rag(options: {
    query: string;
    searchMode?: "advanced" | "basic" | "custom";
    searchSettings?: SearchSettings | Record<string, any>;
    ragGenerationConfig?: GenerationConfig | Record<string, any>;
    taskPromptOverride?: string;
    includeTitleIfAvailable?: boolean;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
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
      ...(options.taskPromptOverride && {
        task_prompt_override: options.taskPromptOverride,
      }),
      ...(options.includeTitleIfAvailable && {
        include_title_if_available: options.includeTitleIfAvailable,
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

  @feature("retrieval.streamRag")
  private async streamRag(
    ragData: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    return this.client.makeRequest<ReadableStream<Uint8Array>>(
      "POST",
      "retrieval/rag",
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
   * Key Features:
   *    - Hybrid search combining vector and knowledge graph approaches
   *    - Contextual conversation management with conversation_id tracking
   *    - Customizable generation parameters for response style and length
   *    - Source document citation with optional title inclusion
   *    - Streaming support for real-time responses
   *
   * Common Use Cases:
   *    - Research assistance and literature review
   *    - Document analysis and summarization
   *    - Technical support and troubleshooting
   *    - Educational Q&A and tutoring
   *    - Knowledge base exploration
   *
   * The agent uses both vector search and knowledge graph capabilities to
   * find and synthesize information, providing detailed, factual responses
   * with proper attribution to source documents.
   * @param message Current message to process
   * @param searchSettings Settings for the search
   * @param ragGenerationConfig Configuration for RAG generation
   * @param taskPromptOverride Optional custom prompt to override default
   * @param includeTitleIfAvailable Include document titles in responses when available
   * @param conversationId ID of the conversation
   * @returns
   */
  @feature("retrieval.agent")
  async agent(options: {
    message: Message;
    searchMode?: "advanced" | "basic" | "custom";
    searchSettings?: SearchSettings | Record<string, any>;
    ragGenerationConfig?: GenerationConfig | Record<string, any>;
    taskPromptOverride?: string;
    includeTitleIfAvailable?: boolean;
    conversationId?: string;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
    const data: Record<string, any> = {
      message: options.message,
      ...(options.searchMode && {
        search_mode: options.searchMode,
      }),
      ...(options.searchSettings && {
        search_settings: ensureSnakeCase(options.searchSettings),
      }),
      ...(options.ragGenerationConfig && {
        rag_generation_config: ensureSnakeCase(options.ragGenerationConfig),
      }),
      ...(options.taskPromptOverride && {
        task_prompt_override: options.taskPromptOverride,
      }),
      ...(options.includeTitleIfAvailable && {
        include_title_if_available: options.includeTitleIfAvailable,
      }),
      ...(options.conversationId && {
        conversation_id: options.conversationId,
      }),
    };

    if (options.ragGenerationConfig && options.ragGenerationConfig.stream) {
      return this.streamAgent(data);
    } else {
      return await this.client.makeRequest("POST", "retrieval/agent", {
        data: data,
      });
    }
  }

  @feature("retrieval.streamAgent")
  private async streamAgent(
    agentData: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    return this.client.makeRequest<ReadableStream<Uint8Array>>(
      "POST",
      "retrieval/agent",
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
  @feature("retrieval.completion")
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

  @feature("retrieval.streamCompletion")
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
}
