import { r2rClient } from "../../r2rClient";
import { WrappedGraphResponse, WrappedGraphsResponse } from "../../types";

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
}
