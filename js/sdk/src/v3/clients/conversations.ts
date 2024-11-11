import { r2rClient } from "../../r2rClient";

export class ConversationsClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new conversation.
   * @returns
   */
  async create(): Promise<any> {
    return this.client.makeRequest("POST", "conversations");
  }

  /**
   * List conversations with pagination and sorting options.
   * @param ids List of conversation IDs to retrieve
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async list(options?: {
    ids?: string[];
    offset?: number;
    limit?: number;
  }): Promise<any> {
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
   * @param branch_id The ID of the branch to retrieve
   * @returns
   */
  async retrieve(options: { id: string; branch_id?: string }): Promise<any> {
    const params: Record<string, any> = {
      branch_id: options.branch_id,
    };

    return this.client.makeRequest("GET", `conversations/${options.id}`, {
      params,
    });
  }

  /**
   * Delete a conversation.
   * @param id The ID of the conversation to delete
   * @returns
   */
  async delete(options: { id: string }): Promise<any> {
    return this.client.makeRequest("DELETE", `conversations/${options.id}`);
  }

  /**
   * Add a new message to a conversation.
   * @param id The ID of the conversation to add the message to
   * @param content The content of the message
   * @param role The role of the message (e.g., "user" or "assistant")
   * @param parent_id The ID of the parent message
   * @param metadata Additional metadata to attach to the message
   * @returns
   */
  async addMessage(options: {
    id: string;
    content: string;
    role: string;
    parent_id?: string;
    metadata?: Record<string, any>;
  }): Promise<any> {
    const data: Record<string, any> = {
      content: options.content,
      role: options.role,
      ...(options.parent_id && { parent_id: options.parent_id }),
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
   * @param message_id The ID of the message to update
   * @param content The new content of the message
   * @returns
   */
  async updateMessage(options: {
    id: string;
    message_id: string;
    content: string;
  }): Promise<any> {
    const data: Record<string, any> = {
      content: options.content,
    };

    return this.client.makeRequest(
      "POST",
      `conversations/${options.id}/messages/${options.message_id}`,
      {
        data,
      },
    );
  }

  /**
   * List all branches in a conversation.
   * @param id The ID of the conversation to list branches for
   * @returns
   */
  async listBranches(options: { id: string }): Promise<any> {
    return this.client.makeRequest(
      "GET",
      `conversations/${options.id}/branches`,
    );
  }
}
