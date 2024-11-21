import { r2rClient } from "../../r2rClient";
import {
  WrappedGraphResponse,
  WrappedBooleanResponse,
  WrappedGraphsResponse,
  WrappedGenericMessageResponse,
  WrappedEntityResponse,
  WrappedEntitiesResponse,
  WrappedRelationshipsResponse,
  WrappedRelationshipResponse,
  WrappedCommunitiesResponse,
  WrappedCommunityResponse,
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

  /**
   * Get detailed information about a specific graph.
   * @param id Graph ID to retrieve
   * @returns
   */
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
   * Delete a graph.
   * @param options
   * @returns
   */
  async delete(options: { id: string }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `graphs/${options.id}`);
  }

  /**
   * FIXME: Should this be `addEntity` or `createEntity`?
   * Add an entity to a graph.
   * @param id Graph ID
   * @param entityId Entity ID to add
   * @returns
   */
  async addEntity(options: {
    id: string;
    entityId: string;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.id}/entities/${options.entityId}`,
    );
  }

  /**
   * Remove an entity from a graph.
   * @param id Graph ID
   * @param entityId Entity ID to remove
   * @returns
   */
  async removeEntity(options: {
    id: string;
    entityId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `graphs/${options.id}/entities/${options.entityId}`,
    );
  }

  /**
   * List all entities in a graph.
   * @param id Graph ID
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listEntities(options: {
    id: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedEntitiesResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest("GET", `graphs/${options.id}/entities`, {
      params,
    });
  }

  /**
   * Retrieve an entity from a graph.
   * @param id Graph ID
   * @param entityId Entity ID to retrieve
   * @returns
   */
  async getEntity(options: {
    id: string;
    entityId: string;
  }): Promise<WrappedEntityResponse> {
    return this.client.makeRequest(
      "GET",
      `graphs/${options.id}/entities/${options.entityId}`,
    );
  }

  /**
   * FIXME: Should this be `addRelationship` or `createRelationship`?
   * Add a relationship to a graph.
   * @param id Graph ID
   * @param relationshipId Relationship ID to add
   * @returns
   */
  async addRelationship(options: {
    id: string;
    relationshipId: string;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.id}/relationships/${options.relationshipId}`,
    );
  }

  /**
   * Remove a relationship from a graph.
   * @param id Graph ID
   * @param relationshipId Relationship ID to remove
   * @returns
   */
  async removeRelationship(options: {
    id: string;
    relationshipId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `graphs/${options.id}/relationships/${options.relationshipId}`,
    );
  }

  /**
   * List all relationships in a graph.
   * @param id Graph ID
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listRelationships(options: {
    id: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedRelationshipsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest(
      "GET",
      `graphs/${options.id}/relationships`,
      {
        params,
      },
    );
  }

  /**
   * Retrieve a relationship from a graph.
   * @param id Graph ID
   * @param relationshipId Relationship ID to retrieve
   * @returns
   */
  async getRelationship(options: {
    id: string;
    relationshipId: string;
  }): Promise<WrappedRelationshipResponse> {
    return this.client.makeRequest(
      "GET",
      `graphs/${options.id}/relationships/${options.relationshipId}`,
    );
  }

  /**
   * FIXME: Should this be `addCommunity` or `createCommunity`?
   * Add a community to a graph.
   * @param id Graph ID
   * @param communityId Community ID to add
   * @returns
   */
  async addCommunity(options: {
    id: string;
    communityId: string;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.id}/communities/${options.communityId}`,
    );
  }

  /**
   * Remove a community from a graph.
   * @param id Graph ID
   * @param communityId Community ID to remove
   * @returns
   */
  async removeCommunity(options: {
    id: string;
    communityId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `graphs/${options.id}/communities/${options.communityId}`,
    );
  }

  /**
   * List all communities in a graph.
   * @param id Graph ID
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listCommunities(options: {
    id: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedCommunitiesResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest("GET", `graphs/${options.id}/communities`, {
      params,
    });
  }

  /**
   * Retrieve a community from a graph.
   * @param id Graph ID
   * @param communityId Community ID to retrieve
   * @returns
   */
  async getCommunity(options: {
    id: string;
    communityId: string;
  }): Promise<WrappedCommunityResponse> {
    return this.client.makeRequest(
      "GET",
      `graphs/${options.id}/communities/${options.communityId}`,
    );
  }
}
