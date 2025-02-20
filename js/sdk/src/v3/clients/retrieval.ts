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
   * @param taskPromptOverride Optional custom prompt to override default
   * @param includeTitleIfAvailable Include document titles in responses when available
   * @returns
   */
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

  private async *streamRag(
    ragData: Record<string, any>,
  ): AsyncGenerator<any, void, unknown> {
    // 1) Make the streaming request with responseType: "stream"
    const responseStream =
      await this.client.makeRequest<ReadableStream<Uint8Array>>(
        "POST",
        "retrieval/rag",
        {
          data: ragData,
          headers: { "Content-Type": "application/json" },
          responseType: "stream", // triggers streaming code in BaseClient
        },
      );

    if (!responseStream) {
      throw new Error("No response stream received");
    }

    const reader = responseStream.getReader();
    const textDecoder = new TextDecoder("utf-8");

    let buffer = "";
    let currentEventType = "unknown";

    while (true) {
      // 2) Read the next chunk
      const { value, done } = await reader.read();
      if (done) {
        break; // end of the stream
      }
      // 3) Decode from bytes to text
      const chunkStr = textDecoder.decode(value, { stream: true });
      // 4) Append to our buffer (which might already have a partial line)
      buffer += chunkStr;

      // 5) Split by newline
      const lines = buffer.split("\n");

      // Keep the last partial line in `buffer`
      buffer = lines.pop() || "";

      // 6) Process each complete line
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith(":")) {
          // SSE "heartbeat" or empty line
          continue;
        }
        if (trimmed.startsWith("event:")) {
          // e.g. event: final_answer
          currentEventType = trimmed.slice("event:".length).trim();
        } else if (trimmed.startsWith("data:")) {
          // e.g. data: {"generated_answer":"DeepSeek R1 ..."}
          const dataStr = trimmed.slice("data:".length).trim();
          const parsedEvent = parseSseEvent({ event: currentEventType, data: dataStr });
          if (parsedEvent !== null) {
            yield parsedEvent;
          }
        }
      }
    }

    // End of stream, if there's leftover in buffer, handle if needed
  }

  //   // In retrieval.ts:
  // private async *streamRag(
  //   ragData: Record<string, any>,
  // ): AsyncGenerator<any, void, unknown> {
  //   // 1) Make the streaming request -> returns a browser ReadableStream<Uint8Array>
  //   const responseStream =
  //     await this.client.makeRequest<ReadableStream<Uint8Array>>(
  //       "POST",
  //       "retrieval/rag",
  //       {
  //         data: ragData,
  //         headers: { "Content-Type": "application/json" },
  //         responseType: "stream",
  //       },
  //     );

  //   if (!responseStream) {
  //     throw new Error("No response stream received");
  //   }

  //   // 2) Get a reader from the stream
  //   const reader = responseStream.getReader();
  //   const textDecoder = new TextDecoder("utf-8");

  //   let buffer = "";
  //   let currentEventType = "unknown";

  //   // 3) Read chunks until done
  //   while (true) {
  //     const { value, done } = await reader.read();
  //     if (done) {
  //       break;
  //     }
  //     // Decode the chunk into a string
  //     const chunkStr = textDecoder.decode(value, { stream: true });
  //     buffer += chunkStr;

  //     // 4) Split on newlines
  //     const lines = buffer.split("\n");
  //     buffer = lines.pop() || ""; // keep the partial line in the buffer

  //     for (const line of lines) {
  //       const trimmed = line.trim();
  //       if (!trimmed || trimmed.startsWith(":")) {
  //         // SSE heartbeats or blank lines
  //         continue;
  //       }
  //       if (trimmed.startsWith("event:")) {
  //         currentEventType = trimmed.slice("event:".length).trim();
  //       } else if (trimmed.startsWith("data:")) {
  //         const dataStr = trimmed.slice("data:".length).trim();
  //         // Attempt to parse the SSE event
  //         const eventObj = parseSseEvent({ event: currentEventType, data: dataStr });
  //         if (eventObj != null) {
  //           yield eventObj;
  //         }
  //       }
  //     }
  //   }
  // }

  // private async streamRag(
  //   ragData: Record<string, any>,
  // ): Promise<ReadableStream<Uint8Array>> {
  //   return this.client.makeRequest<ReadableStream<Uint8Array>>(
  //     "POST",
  //     "retrieval/rag",
  //     {
  //       data: ragData,
  //       headers: {
  //         "Content-Type": "application/json",
  //       },
  //       responseType: "stream",
  //     },
  //   );
  // }

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
   * @param ragGenerationConfig Configuration for RAG generation
   * @param searchMode Search mode to use, either "basic", "advanced", or "custom"
   * @param searchSettings Settings for the search
   * @param taskPromptOverride Optional custom prompt to override default
   * @param includeTitleIfAvailable Include document titles in responses when available
   * @param conversationId ID of the conversation
   * @param tools List of tool configurations
   * @param maxToolContextLength Maximum context length for tool replies
   * @param useExtendedPrompt Use extended prompt for generation
   * @returns
   */
  async agent(options: {
    message: Message;
    ragGenerationConfig?: GenerationConfig | Record<string, any>;
    searchMode?: "basic" | "advanced" | "custom";
    searchSettings?: SearchSettings | Record<string, any>;
    taskPromptOverride?: string;
    includeTitleIfAvailable?: boolean;
    conversationId?: string;
    maxToolContextLength?: number;
    tools?: Array<Record<string, any>>;
    useSystemContext?: boolean;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
    const data: Record<string, any> = {
      message: options.message,
      ...(options.searchMode && {
        search_mode: options.searchMode,
      }),
      ...(options.ragGenerationConfig && {
        rag_generation_config: ensureSnakeCase(options.ragGenerationConfig),
      }),
      ...(options.searchSettings && {
        search_settings: ensureSnakeCase(options.searchSettings),
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
      ...(options.tools && {
        tools: options.tools,
      }),
      ...(options.maxToolContextLength && {
        max_tool_context_length: options.maxToolContextLength,
      }),
      ...(options.tools && {
        tools: options.tools,
      }),
      ...(typeof options.useSystemContext !== "undefined" && {
        use_system_context: options.useSystemContext,
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

  private async *streamAgent(
    agentData: Record<string, any>,
  ): AsyncGenerator<any, void, unknown> {
    // 1) Make a streaming request to your "retrieval/agent" endpoint
    //    We'll get back a browser `ReadableStream<Uint8Array>` or a Node stream (depending on environment).
    const responseStream = await this.client.makeRequest<ReadableStream<Uint8Array>>(
      "POST",
      "retrieval/agent",
      {
        data: agentData,
        headers: { "Content-Type": "application/json" },
        responseType: "stream",
      },
    );

    if (!responseStream) {
      throw new Error("No response stream received from agent endpoint");
    }

    // 2) Prepare to read the SSE stream line-by-line
    const reader = responseStream.getReader();
    const textDecoder = new TextDecoder("utf-8");

    let buffer = "";
    let currentEventType = "unknown";

    // 3) Read chunks until the stream closes
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break; // end of stream
      }
      // Convert bytes to text
      const chunkStr = textDecoder.decode(value, { stream: true });
      buffer += chunkStr;

      // SSE messages are separated by newlines
      const lines = buffer.split("\n");
      // The last element might be a partial line, so re-buffer it
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        // Ignore empty lines or lines starting with ":"
        if (!trimmed || trimmed.startsWith(":")) {
          continue;
        }
        if (trimmed.startsWith("event:")) {
          // e.g. "event: message"
          currentEventType = trimmed.slice("event:".length).trim();
        } else if (trimmed.startsWith("data:")) {
          // e.g. "data: {...}"
          const dataStr = trimmed.slice("data:".length).trim();
          const parsed = parseSseEvent({ event: currentEventType, data: dataStr });
          if (parsed !== null) {
            yield parsed;
          }
        }
      }
    }

    // If anything remains in `buffer`, handle it if needed.
    // In most SSE flows, we expect the final chunk to end with a newline.
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
