import { r2rClient } from "../../r2rClient";

export class CollectionsClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new collection.
   * @param name Name of the collection
   * @param description Optional description of the collection
   * @returns Created collection information
   */
  async create(name: string, description?: string): Promise<any> {
    const data = {
      name,
      ...(description && { description }),
    };

    return this.client.makeRequest("POST", "collections", { data });
  }

  // TODO: left a review comment about some inconsistency in the API. Review after that is addressed.
  async list(options?: { offset?: number; limit?: number }): Promise<any> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest("GET", "collections", {
      params,
    });
  }

  async retrieve(id: string): Promise<any> {
    return this.client.makeRequest("GET", `collections/${id}`);
  }

  async update(id: string, name?: string, description?: string): Promise<any> {
    const data = {
      ...(name && { name }),
      ...(description && { description }),
    };

    return this.client.makeRequest("PATCH", `collections/${id}`, { data });
  }

  async delete(id: string): Promise<any> {
    return this.client.makeRequest("DELETE", `collections/${id}`);
  }

  async list_documents(
    id: string,
    options?: {
      offset?: number;
      limit?: number;
    },
  ): Promise<any> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest("GET", `collections/${id}/documents`, {
      params,
    });
  }

  async add_document(id: string, documentId: string): Promise<any> {
    return this.client.makeRequest(
      "POST",
      `collections/${id}/documents/${documentId}`,
    );
  }

  async remove_document(id: string, documentId: string): Promise<any> {
    return this.client.makeRequest(
      "DELETE",
      `collections/${id}/documents/${documentId}`,
    );
  }

  async list_users(
    id: string,
    options?: {
      offset?: number;
      limit?: number;
    },
  ): Promise<any> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest("GET", `collections/${id}/users`, {
      params,
    });
  }

  async add_user(id: string, userId: string): Promise<any> {
    return this.client.makeRequest("POST", `collections/${id}/users/${userId}`);
  }

  async remove_user(id: string, userId: string): Promise<any> {
    return this.client.makeRequest(
      "DELETE",
      `collections/${id}/users/${userId}`,
    );
  }
}
