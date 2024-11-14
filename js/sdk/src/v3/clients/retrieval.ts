import { r2rClient } from "../../r2rClient";

import {
  LoginResponse,
  TokenInfo,
  Message,
  RefreshTokenResponse,
  VectorSearchSettings,
  KGSearchSettings,
  KGRunType,
  KGCreationSettings,
  KGEnrichmentSettings,
  KGEntityDeduplicationSettings,
  GenerationConfig,
  RawChunk,
} from "../../models";

export class RetrievalClient {
  constructor(private client: r2rClient) {}

  async search(options: {
    query: string;
    vector_search_settings?: VectorSearchSettings | Record<string, any>;
    kg_search_settings?: KGSearchSettings | Record<string, any>;
  }): Promise<any> {
    const data = {
      query: options.query,
      ...(options.vector_search_settings && {
        vector_search_settings: options.vector_search_settings,
      }),
      ...(options.kg_search_settings && {
        kg_search_settings: options.kg_search_settings,
      }),
    };

    return await this.client.makeRequest("POST", "retrieval/search", {
      data: data,
    });
  }

  async rag(options: {
    query: string;
    vector_search_settings?: VectorSearchSettings | Record<string, any>;
    kg_search_settings?: KGSearchSettings | Record<string, any>;
    generation_config?: GenerationConfig | Record<string, any>;
    task_prompt_override?: string;
    include_title_if_available?: boolean;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
    const data = {
      query: options.query,
      ...(options.vector_search_settings && {
        vector_search_settings: options.vector_search_settings,
      }),
      ...(options.kg_search_settings && {
        kg_search_settings: options.kg_search_settings,
      }),
      ...(options.generation_config && {
        generation_config: options.generation_config,
      }),
      ...(options.task_prompt_override && {
        task_prompt_override: options.task_prompt_override,
      }),
      ...(options.include_title_if_available && {
        include_title_if_available: options.include_title_if_available,
      }),
    };

    if (options.generation_config && options.generation_config.stream) {
      return this.streamRag(data);
    } else {
      return await this.client.makeRequest("POST", "retrieval/rag", {
        data: data,
      });
    }
  }

  private async streamRag(
    rag_data: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    return this.client.makeRequest<ReadableStream<Uint8Array>>(
      "POST",
      "retrieval/rag",
      {
        data: rag_data,
        headers: {
          "Content-Type": "application/json",
        },
        responseType: "stream",
      },
    );
  }

  async agent(options: {
    messages: Message[];
    generation_config?: GenerationConfig | Record<string, any>;
    vector_search_settings?: VectorSearchSettings | Record<string, any>;
    kg_search_settings?: KGSearchSettings | Record<string, any>;
    task_prompt_override?: string;
    include_title_if_available?: boolean;
    conversation_id?: string;
    branch_id?: string;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
    const data: Record<string, any> = {
      messages: options.messages,
      ...(options.vector_search_settings && {
        vector_search_settings: options.vector_search_settings,
      }),
      ...(options.kg_search_settings && {
        kg_search_settings: options.kg_search_settings,
      }),
      ...(options.generation_config && {
        generation_config: options.generation_config,
      }),
      ...(options.task_prompt_override && {
        task_prompt_override: options.task_prompt_override,
      }),
      ...(options.include_title_if_available && {
        include_title_if_available: options.include_title_if_available,
      }),
      ...(options.conversation_id && {
        conversation_id: options.conversation_id,
      }),
      ...(options.branch_id && {
        branch_id: options.branch_id,
      }),
    };

    if (options.generation_config && options.generation_config.stream) {
      return this.streamAgent(data);
    } else {
      return await this.client.makeRequest("POST", "retrieval/agent", {
        data: data,
      });
    }
  }

  private async streamAgent(
    agent_data: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    return this.client.makeRequest<ReadableStream<Uint8Array>>(
      "POST",
      "retrieval/agent",
      {
        data: agent_data,
        headers: {
          "Content-Type": "application/json",
        },
        responseType: "stream",
      },
    );
  }

  async completion(options: {
    messages: Message[];
    generation_config?: GenerationConfig | Record<string, any>;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
    const data = {
      messages: options.messages,
      ...(options.generation_config && {
        generation_config: options.generation_config,
      }),
    };

    if (options.generation_config && options.generation_config.stream) {
      return this.streamCompletion(data);
    } else {
      return await this.client.makeRequest("POST", "retrieval/completion", {
        data: data,
      });
    }
  }

  private async streamCompletion(
    rag_data: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    return this.client.makeRequest<ReadableStream<Uint8Array>>(
      "POST",
      "retrieval/completion",
      {
        data: rag_data,
        headers: {
          "Content-Type": "application/json",
        },
        responseType: "stream",
      },
    );
  }
}
