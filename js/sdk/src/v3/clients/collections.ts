import { r2rClient } from "../../r2rClient";
import {
  WrappedBooleanResponse,
  WrappedGenericMessageResponse,
  WrappedCollectionResponse,
  WrappedCollectionsResponse,
  WrappedDocumentsResponse,
  WrappedUsersResponse,
} from "../../types";

export class CollectionsClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new collection.
   * @param name Name of the collection
   * @param description Optional description of the collection
   * @returns A promise that resolves with the created collection
   */
  async create(options: {
    name: string;
    description?: string;
  }): Promise<WrappedCollectionResponse> {
    return this.client.makeRequest("POST", "collections", {
      data: options,
    });
  }

  /**
   * List collections with pagination and filtering options.
   * @param ids Optional list of collection IDs to filter by
   * @param offset Optional offset for pagination
   * @param limit Optional limit for pagination
   * @returns
   */
  async list(options?: {
    ids?: string[];
    offset?: number;
    limit?: number;
  }): Promise<WrappedCollectionsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.ids && options.ids.length > 0) {
      params.ids = options.ids;
    }

    return this.client.makeRequest("GET", "collections", {
      params,
    });
  }

  /**
   * Get detailed information about a specific collection.
   * @param id Collection ID to retrieve
   * @returns
   */
  async retrieve(options: { id: string }): Promise<WrappedCollectionResponse> {
    return this.client.makeRequest("GET", `collections/${options.id}`);
  }

  /**
   * Update an existing collection.
   * @param id Collection ID to update
   * @param name Optional new name for the collection
   * @param description Optional new description for the collection
   * @returns
   */
  async update(options: {
    id: string;
    name?: string;
    description?: string;
  }): Promise<WrappedCollectionResponse> {
    const data = {
      ...(options.name && { name: options.name }),
      ...(options.description && { description: options.description }),
    };

    return this.client.makeRequest("POST", `collections/${options.id}`, {
      data,
    });
  }

  /**
   * Delete a collection.
   * @param id Collection ID to delete
   * @returns
   */
  async delete(options: { id: string }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `collections/${options.id}`);
  }

  /**
   * List all documents in a collection.
   * @param id Collection ID
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listDocuments(options: {
    id: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedDocumentsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest(
      "GET",
      `collections/${options.id}/documents`,
      {
        params,
      },
    );
  }

  /**
   * Add a document to a collection.
   * @param id Collection ID
   * @param documentId Document ID to add
   * @returns
   */
  async addDocument(options: {
    id: string;
    documentId: string;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest(
      "POST",
      `collections/${options.id}/documents/${options.documentId}`,
    );
  }

  /**
   * Remove a document from a collection.
   * @param id Collection ID
   * @param documentId Document ID to remove
   * @returns
   */
  async removeDocument(options: {
    id: string;
    documentId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `collections/${options.id}/documents/${options.documentId}`,
    );
  }

  /**
   * List all users in a collection.
   * @param id Collection ID
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listUsers(options: {
    id: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedUsersResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest("GET", `collections/${options.id}/users`, {
      params,
    });
  }

  /**
   * Add a user to a collection.
   * @param id Collection ID
   * @param userId User ID to add
   * @returns
   */
  async addUser(options: {
    id: string;
    userId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "POST",
      `collections/${options.id}/users/${options.userId}`,
    );
  }

  /**
   * Remove a user from a collection.
   * @param id Collection ID
   * @param userId User ID to remove
   * @returns
   */
  async removeUser(options: {
    id: string;
    userId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `collections/${options.id}/users/${options.userId}`,
    );
  }
}
