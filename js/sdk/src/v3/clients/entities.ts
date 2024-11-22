import { r2rClient } from "../../r2rClient";
import {
  WrappedBooleanResponse,
  WrappedEntitiesResponse,
  WrappedEntityResponse,
} from "../../types";

export class EntitiesClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new entity.
   * @param name Name of the entity
   * @param description Description of the entity
   * @param attributes Optional list of attributes
   * @param category Optional category
   * @returns The created graph
   */
  async create(options: {
    name: string;
    description: string;
    attributes?: Record<string, any>;
    category?: string;
  }): Promise<WrappedEntityResponse> {
    return this.client.makeRequest("POST", "entities", {
      data: options,
    });
  }

  /**
   * List graphs with pagination and filtering options.
   * @param ids Optional list of graph IDs to filter by
   * @param offset Optional offset for pagination
   * @param limit Optional limit for pagination
   * @returns
   */
  async list(options?: {
    ids?: string[];
    offset?: number;
    limit?: number;
  }): Promise<WrappedEntitiesResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.ids && options.ids.length > 0) {
      params.ids = options.ids;
    }

    return this.client.makeRequest("GET", "entities", {
      params,
    });
  }

  /**
   * Get detailed information about a specific graph.
   * @param id Graph ID to retrieve
   * @returns
   */
  async retrieve(options: { id: string }): Promise<WrappedEntityResponse> {
    return this.client.makeRequest("GET", `entities/${options.id}`);
  }

  /**
   * Update an existing graph.
   * @param id Graph ID to update
   * @param name Optional new name for the graph
   * @param description Optional new description for the graph
   * @returns
   */
  async update(options: {
    id: string;
    name?: string;
    description?: string;
    attributes?: Record<string, any>;
    category?: string;
  }): Promise<WrappedEntityResponse> {
    const data = {
      ...(options.name && { name: options.name }),
      ...(options.description && { description: options.description }),
      ...(options.attributes && { attributes: options.attributes }),
      ...(options.category && { category: options.category }),
    };

    return this.client.makeRequest("POST", `entities/${options.id}`, {
      data,
    });
  }

  /**
   *
   * @param options
   * @returns
   */
  async delete(options: { id: string }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `entities/${options.id}`);
  }
}
