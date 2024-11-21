import { r2rClient } from "../../r2rClient";
import {
  WrappedGraphResponse,
  WrappedBooleanResponse,
  WrappedGraphsResponse,
} from "../../types";

export class GraphsClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new graph.
   * @param name Name of the graph
   * @param description Optional description of the graph
   * @returns The created graph
   */
  async create(options: {
    name: string;
    description?: string;
  }): Promise<WrappedGraphResponse> {
    return this.client.makeRequest("POST", "graphs", {
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
  }): Promise<WrappedGraphsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.ids && options.ids.length > 0) {
      params.ids = options.ids;
    }

    return this.client.makeRequest("GET", "graphs", {
      params,
    });
  }

  async retrieve(options: { id: string }): Promise<WrappedGraphResponse> {
    return this.client.makeRequest("GET", `graphs/${options.id}`);
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
  }): Promise<WrappedGraphResponse> {
    const data = {
      ...(options.name && { name: options.name }),
      ...(options.description && { description: options.description }),
    };

    return this.client.makeRequest("POST", `graphs/${options.id}`, {
      data,
    });
  }

  /**
   *
   * @param options
   * @returns
   */
  async delete(options: { id: string }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `graphs/${options.id}`);
  }
}
