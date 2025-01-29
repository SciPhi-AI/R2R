import { r2rClient } from "../../r2rClient";
import {
  WrappedBooleanResponse,
  WrappedConversationMessagesResponse,
  WrappedConversationResponse,
  WrappedConversationsResponse,
  WrappedMessageResponse,
} from "../../types";
import { downloadBlob } from "../../utils";

let fs: any;
if (typeof window === "undefined") {
  fs = require("fs");
}
export class ConversationsClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new conversation.
   * @param name The name of the conversation
   * @returns The created conversation
   */
  async create(options?: {
    name?: string;
  }): Promise<WrappedConversationResponse> {
    const data: Record<string, any> = {
      ...(options?.name && { name: options?.name }),
    };

    return this.client.makeRequest("POST", "conversations", {
      data,
    });
  }

  /**
   * List conversations with pagination and sorting options.
   * @param ids List of conversation IDs to retrieve
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns A list of conversations
   */
  async list(options?: {
    ids?: string[];
    offset?: number;
    limit?: number;
  }): Promise<WrappedConversationsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.ids && options.ids.length > 0) {
      params.ids = options.ids;
    }

    return this.client.makeRequest("GET", "conversations", {
      params,
    });
  }

  /**
   * Get detailed information about a specific conversation.
   * @param id The ID of the conversation to retrieve
   * @returns The conversation
   */
  async retrieve(options: {
    id: string;
  }): Promise<WrappedConversationMessagesResponse> {
    return this.client.makeRequest("GET", `conversations/${options.id}`);
  }

  /**
   * Update an existing conversation.
   * @param id The ID of the conversation to update
   * @param name The new name of the conversation
   * @returns The updated conversation
   */
  async update(options: {
    id: string;
    name: string;
  }): Promise<WrappedConversationResponse> {
    const data: Record<string, any> = {
      name: options.name,
    };

    return this.client.makeRequest("POST", `conversations/${options.id}`, {
      data,
    });
  }

  /**
   * Delete a conversation.
   * @param id The ID of the conversation to delete
   * @returns Whether the conversation was successfully deleted
   */
  async delete(options: { id: string }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `conversations/${options.id}`);
  }

  /**
   * Add a new message to a conversation.
   * @param id The ID of the conversation to add the message to
   * @param content The content of the message
   * @param role The role of the message (e.g., "user" or "assistant")
   * @param parentID The ID of the parent message
   * @param metadata Additional metadata to attach to the message
   * @returns The created message
   */
  async addMessage(options: {
    id: string;
    content: string;
    role: string;
    parentID?: string;
    metadata?: Record<string, any>;
  }): Promise<WrappedMessageResponse> {
    const data: Record<string, any> = {
      content: options.content,
      role: options.role,
      ...(options.parentID && { parentID: options.parentID }),
      ...(options.metadata && { metadata: options.metadata }),
    };

    return this.client.makeRequest(
      "POST",
      `conversations/${options.id}/messages`,
      {
        data,
      },
    );
  }

  /**
   * Update an existing message in a conversation.
   * @param id The ID of the conversation containing the message
   * @param messageID The ID of the message to update
   * @param content The new content of the message
   * @param metadata Additional metadata to attach to the message
   * @returns The updated message
   */
  async updateMessage(options: {
    id: string;
    messageID: string;
    content?: string;
    metadata?: Record<string, any>;
  }): Promise<any> {
    const data: Record<string, any> = {
      ...(options.content && { content: options.content }),
      ...(options.metadata && { metadata: options.metadata }),
    };

    return this.client.makeRequest(
      "POST",
      `conversations/${options.id}/messages/${options.messageID}`,
      {
        data,
      },
    );
  }

  /**
   * Export conversations as a CSV file with support for filtering and column selection.
   *
   * @param options Export configuration options
   * @param options.outputPath Path where the CSV file should be saved (Node.js only)
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which conversations are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   * @returns Promise<Blob> in browser environments, Promise<void> in Node.js
   */
  async export(
    options: {
      outputPath?: string;
      columns?: string[];
      filters?: Record<string, any>;
      includeHeader?: boolean;
    } = {},
  ): Promise<Blob | void> {
    const data: Record<string, any> = {
      include_header: options.includeHeader ?? true,
    };

    if (options.columns) {
      data.columns = options.columns;
    }
    if (options.filters) {
      data.filters = options.filters;
    }

    const response = await this.client.makeRequest(
      "POST",
      "conversations/export",
      {
        data,
        responseType: "arraybuffer",
        headers: { Accept: "text/csv" },
      },
    );

    // Node environment
    if (options.outputPath && typeof process !== "undefined") {
      await fs.promises.writeFile(options.outputPath, Buffer.from(response));
      return;
    }

    // Browser
    return new Blob([response], { type: "text/csv" });
  }

  /**
   * Export users as a CSV file and save it to the user's device.
   * @param filename
   * @param options
   */
  async exportToFile(options: {
    filename: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    const blob = await this.export(options);
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    }
  }

  /**
   * Export messages as a CSV file with support for filtering and column selection.
   *
   * @param options Export configuration options
   * @param options.outputPath Path where the CSV file should be saved (Node.js only)
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which messages are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   * @returns Promise<Blob> in browser environments, Promise<void> in Node.js
   */
  async exportMessages(
    options: {
      outputPath?: string;
      columns?: string[];
      filters?: Record<string, any>;
      includeHeader?: boolean;
    } = {},
  ): Promise<Blob | void> {
    const data: Record<string, any> = {
      include_header: options.includeHeader ?? true,
    };

    if (options.columns) {
      data.columns = options.columns;
    }
    if (options.filters) {
      data.filters = options.filters;
    }

    const response = await this.client.makeRequest(
      "POST",
      "conversations/export_messages",
      {
        data,
        responseType: "arraybuffer",
        headers: { Accept: "text/csv" },
      },
    );

    // Node environment
    if (options.outputPath && typeof process !== "undefined") {
      await fs.promises.writeFile(options.outputPath, Buffer.from(response));
      return;
    }

    // Browser
    return new Blob([response], { type: "text/csv" });
  }

  /**
   * Export messages as a CSV file and save it to the user's device.
   * @param filename
   * @param options
   */
  async exportMessagesToFile(options: {
    filename: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    const blob = await this.exportMessages(options);
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    }
  }
}
