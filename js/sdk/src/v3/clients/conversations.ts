import { feature } from "../../feature";
import { r2rClient } from "../../r2rClient";
import {
  WrappedBooleanResponse,
  WrappedConversationMessagesResponse,
  WrappedConversationResponse,
  WrappedConversationsResponse,
  WrappedMessageResponse,
} from "../../types";

export class ConversationsClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new conversation.
   * @returns
   */
  @feature("conversations.create")
  async create(): Promise<WrappedConversationResponse> {
    return this.client.makeRequest("POST", "conversations");
  }

  /**
   * List conversations with pagination and sorting options.
   * @param ids List of conversation IDs to retrieve
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  @feature("conversations.list")
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
   * @returns
   */
  @feature("conversations.retrieve")
  async retrieve(options: {
    id: string;
  }): Promise<WrappedConversationMessagesResponse> {
    return this.client.makeRequest("GET", `conversations/${options.id}`);
  }

  /**
   * Delete a conversation.
   * @param id The ID of the conversation to delete
   * @returns
   */
  @feature("conversations.delete")
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
   * @returns
   */
  @feature("conversations.addMessage")
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
   * @returns
   */
  @feature("conversations.updateMessage")
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
}
