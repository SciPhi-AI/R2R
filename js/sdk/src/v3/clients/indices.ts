import { r2rClient } from "../../r2rClient";
import { IndexConfig } from "../../types";

export class IndiciesClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new vector similarity search index in the database.
   * @param config Configuration for the vector index.
   * @param run_with_orchestration Whether to run index creation as an orchestrated task.
   * @returns
   */
  async create(options: {
    config: IndexConfig;
    run_with_orchestration?: boolean;
  }): Promise<any> {
    const data = {
      config: options.config,
      ...(options.run_with_orchestration && {
        run_with_orchestration: options.run_with_orchestration,
      }),
    };

    return this.client.makeRequest("POST", `indices`, {
      data,
    });
  }

  /**
   * List existing vector similarity search indices with pagination support.
   * @param filters Filter criteria for indices.
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async list(options?: {
    filters?: Record<string, any>;
    offset?: number;
    limit?: number;
  }): Promise<any> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.filters) {
      params.filters = options.filters;
    }

    return this.client.makeRequest("GET", `indices`, {
      params,
    });
  }

  /**
   * Get detailed information about a specific vector index.
   * @param index_name The name of the index to retrieve.
   * @param table_name The name of the table where the index is stored.
   * @returns
   */
  async retrieve(options: {
    table_name: string;
    index_name: string;
  }): Promise<any> {
    return this.client.makeRequest(
      "GET",
      `indices/${options.index_name}/${options.table_name}`,
    );
  }

  /**
   * Delete an existing vector index.
   * @param index_name The name of the index to delete.
   * @param table_name The name of the table where the index is stored.
   * @returns
   */
  async delete(options: {
    table_name: string;
    index_name: string;
  }): Promise<any> {
    return this.client.makeRequest(
      "DELETE",
      `indices/${options.index_name}/${options.table_name}`,
    );
  }
}