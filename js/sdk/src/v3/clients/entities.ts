import { r2rClient } from "../../r2rClient";
import {
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
    attributes?: string[];
    category?: string;
  }): Promise<WrappedEntityResponse> {
    return this.client.makeRequest("POST", "graphs", {
      data: options,
    });
  }
}
