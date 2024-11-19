import { r2rClient } from "../../r2rClient";

import {
  Message,
  VectorSearchSettings,
  KGSearchSettings,
  GenerationConfig,
} from "../../models";

export class RetrievalClient {
  constructor(private client: r2rClient) {}

  async search(options: {
    query: string;
    vectorSearchSettings?: VectorSearchSettings | Record<string, any>;
    kgSearchSettings?: KGSearchSettings | Record<string, any>;
  }): Promise<any> {
    const data = {
      query: options.query,
      ...(options.vectorSearchSettings && {
        vectorSearchSettings: options.vectorSearchSettings,
      }),
      ...(options.kgSearchSettings && {
        kgSearchSettings: options.kgSearchSettings,
      }),
    };

    return await this.client.makeRequest("POST", "retrieval/search", {
      data: data,
    });
  }

  async rag(options: {
    query: string;
    vectorSearchSettings?: VectorSearchSettings | Record<string, any>;
    kgSearchSettings?: KGSearchSettings | Record<string, any>;
    generationConfig?: GenerationConfig | Record<string, any>;
    taskPromptOverride?: string;
    includeTitleIfAvailable?: boolean;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
    const data = {
      query: options.query,
      ...(options.vectorSearchSettings && {
        vectorSearchSettings: options.vectorSearchSettings,
      }),
      ...(options.kgSearchSettings && {
        kgSearchSettings: options.kgSearchSettings,
      }),
      ...(options.generationConfig && {
        generationConfig: options.generationConfig,
      }),
      ...(options.taskPromptOverride && {
        taskPromptOverride: options.taskPromptOverride,
      }),
      ...(options.includeTitleIfAvailable && {
        includeTitleIfAvailable: options.includeTitleIfAvailable,
      }),
    };

    if (options.generationConfig && options.generationConfig.stream) {
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
        headers: {
          "Content-Type": "application/json",
        },
        responseType: "stream",
      },
    );
  }

  async agent(options: {
    messages: Message[];
    generationConfig?: GenerationConfig | Record<string, any>;
    vectorSearchSettings?: VectorSearchSettings | Record<string, any>;
    kgSearchSettings?: KGSearchSettings | Record<string, any>;
    taskPromptOverride?: string;
    includeTitleIfAvailable?: boolean;
    conversationId?: string;
    branchId?: string;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
    const data: Record<string, any> = {
      messages: options.messages,
      ...(options.vectorSearchSettings && {
        vectorSearchSettings: options.vectorSearchSettings,
      }),
      ...(options.kgSearchSettings && {
        kgSearchSettings: options.kgSearchSettings,
      }),
      ...(options.generationConfig && {
        generationConfig: options.generationConfig,
      }),
      ...(options.taskPromptOverride && {
        taskPromptOverride: options.taskPromptOverride,
      }),
      ...(options.includeTitleIfAvailable && {
        includeTitleIfAvailable: options.includeTitleIfAvailable,
      }),
      ...(options.conversationId && {
        conversationId: options.conversationId,
      }),
      ...(options.branchId && {
        branchId: options.branchId,
      }),
    };

    if (options.generationConfig && options.generationConfig.stream) {
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

  async completion(options: {
    messages: Message[];
    generationConfig?: GenerationConfig | Record<string, any>;
  }): Promise<any | AsyncGenerator<string, void, unknown>> {
    const data = {
      messages: options.messages,
      ...(options.generationConfig && {
        generationConfig: options.generationConfig,
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
}
